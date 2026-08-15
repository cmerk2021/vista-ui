from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .. import db
from ..bus import bus
from ..config import get_settings
from ..push import notifier
from ..security import decrypt_secret
from . import protocol as p
from .protocol import ARMED_STATES
from .state import PanelState

log = logging.getLogger("tpi")


class AuthError(Exception):
    pass


# ContactID code classification (partial; full lists are widely available).
def classify_cid(ev: p.CidEvent) -> tuple[str, str, bool]:
    """Return (event_type, severity, should_push) for a CID event."""
    code = ev.code
    restore = ev.is_restore
    if 100 <= code <= 199:  # Fire / panic / medical / burglary alarms
        return ("alarm", "info" if restore else "alarm", not restore)
    if code in (301,):  # AC loss
        return ("ac_trouble", "info" if restore else "warning", not restore)
    if code in (302, 338, 384):  # Low battery (system / zone / RF)
        return ("low_battery", "info" if restore else "warning", not restore)
    if 300 <= code <= 399:  # System troubles
        return ("trouble", "info" if restore else "warning", not restore)
    if 400 <= code <= 499:  # Open / close (arm / disarm) - pushed via partition state
        return ("arm_disarm", "info", False)
    if 570 <= code <= 579:  # Bypass
        return ("bypass", "info", False)
    return ("cid", "info", False)


class TpiClient:
    def __init__(self) -> None:
        self.state = PanelState()
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._buffer = ""
        self._write_lock = asyncio.Lock()
        self._stop = False
        self._supervisor: Optional[asyncio.Task] = None
        self._reconnect_signal = asyncio.Event()
        self._session_established = False

    # --- lifecycle ----------------------------------------------------------

    async def start(self) -> None:
        self._stop = False
        self._supervisor = asyncio.create_task(self._supervise())

    async def stop(self) -> None:
        self._stop = True
        if self._writer is not None:
            self._writer.close()
        if self._supervisor is not None:
            self._supervisor.cancel()

    def request_reconnect(self) -> None:
        """Trigger a reconnect (e.g. after connection settings change)."""
        self._reconnect_signal.set()
        if self._writer is not None:
            self._writer.close()

    async def _config(self) -> tuple[str, int, str]:
        s = get_settings()
        host = await db.get_setting("panel.host") or s.evl_host
        port = int(await db.get_setting("panel.port") or s.evl_port)
        pw = decrypt_secret(await db.get_setting("panel.password")) or s.evl_password
        return host, port, pw

    async def _user_code(self) -> Optional[str]:
        return decrypt_secret(await db.get_setting("panel.user_code"))

    async def _supervise(self) -> None:
        backoff = 2
        while not self._stop:
            self._session_established = False
            try:
                await self._connect_once()
            except asyncio.CancelledError:
                raise
            except AuthError as exc:
                log.error("Envisalink login failed: %s", exc)
                self._set_disconnected()
                backoff = 30
            except Exception as exc:  # noqa: BLE001 - network layer, keep looping
                log.warning("Envisalink connection lost: %s", exc)
                self._set_disconnected()
            # A drop after we were logged in is transient (e.g. the EVL closing an
            # idle socket); reconnect promptly instead of backing off.
            if self._session_established:
                backoff = 1
            if self._stop:
                break
            self._reconnect_signal.clear()
            try:
                await asyncio.wait_for(self._reconnect_signal.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
            if not self._session_established:
                backoff = min(backoff * 2, 30)

    def _set_disconnected(self) -> None:
        self.state.connected = False
        self.state.logged_in = False
        bus.publish({"type": "status", "state": self.state.to_dict()})

    async def _connect_once(self) -> None:
        host, port, password = await self._config()
        log.info("Connecting to Envisalink at %s:%s", host, port)
        reader, writer = await asyncio.open_connection(host, port)
        self._reader, self._writer = reader, writer
        self._buffer = ""
        self.state.connected = True
        await self._login(reader, writer, password)
        self.state.logged_in = True
        self._session_established = True
        bus.publish({"type": "status", "state": self.state.to_dict()})
        await db.insert_event(event_type="connected", detail=f"Connected to {host}:{port}")

        poll_task = asyncio.create_task(self._poll_loop())
        try:
            await self._read_loop(reader)
        finally:
            poll_task.cancel()

    async def _login(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, password: str) -> None:
        # Wait up to 10s for the "Login:" prompt.
        buf = ""
        while "login" not in buf.lower():
            chunk = await asyncio.wait_for(reader.read(1024), timeout=10)
            if not chunk:
                raise AuthError("connection closed before login prompt")
            buf += chunk.decode(errors="ignore")

        writer.write((password + "\r\n").encode())
        await writer.drain()

        buf = ""
        while True:
            chunk = await asyncio.wait_for(reader.read(1024), timeout=10)
            if not chunk:
                raise AuthError("connection closed during login")
            buf += chunk.decode(errors="ignore").upper()
            if "OK" in buf:
                # Consume any framed data that arrived alongside "OK".
                self._buffer += buf[buf.find("OK") + 2 :]
                return
            if "FAILED" in buf:
                raise AuthError("password rejected")
            if "TIMED OUT" in buf:
                raise AuthError("login timed out")

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        while not self._stop:
            data = await reader.read(4096)
            if not data:
                raise ConnectionError("Envisalink closed the connection")
            self._buffer += data.decode(errors="ignore")
            for frame in self._extract_frames():
                await self._dispatch(frame)

    def _extract_frames(self) -> list[str]:
        """Pull complete %...$ / ^...$ frames out of the buffer."""
        frames: list[str] = []
        while True:
            pct = self._buffer.find("%")
            crt = self._buffer.find("^")
            starts = [i for i in (pct, crt) if i != -1]
            if not starts:
                break
            start = min(starts)
            end = self._buffer.find("$", start)
            if end == -1:
                self._buffer = self._buffer[start:]  # keep partial frame
                break
            frames.append(self._buffer[start : end + 1])
            self._buffer = self._buffer[end + 1 :]
        return frames

    # --- outbound commands --------------------------------------------------

    async def _write(self, text: str) -> None:
        if self._writer is None:
            raise ConnectionError("not connected")
        async with self._write_lock:
            self._writer.write(text.encode())
            await self._writer.drain()

    async def send_command(self, cc: str, data: str = "") -> None:
        # The comma is mandatory even when there is no data.
        await self._write(f"^{cc},{data}$")

    async def poll(self) -> None:
        await self.send_command(p.CMD_POLL)

    async def dump_zone_timers(self) -> None:
        await self.send_command(p.CMD_DUMP_ZONE_TIMERS)

    async def change_default_partition(self, partition: int) -> None:
        await self.send_command(p.CMD_CHANGE_DEFAULT_PARTITION, str(partition))
        self.state.default_partition = partition

    async def send_keys(self, keys: str, partition: int = 1) -> None:
        """Send each keystroke to a specific partition via command 03."""
        for key in keys:
            await self.send_command(p.CMD_KEYPRESS_PARTITION, f"{partition},{key}")
            await asyncio.sleep(0.05)

    # Vista arming macros. These keystroke sequences are standard Ademco/Vista
    # panel behavior; the TPI doc defines only the keystroke transport, not the
    # panel's arming semantics.
    async def _require_code(self) -> str:
        code = await self._user_code()
        if not code:
            raise ValueError("Panel user code is not configured (Settings).")
        return code

    async def arm_away(self, partition: int = 1) -> None:
        await self.send_keys(await self._require_code() + "2", partition)

    async def arm_stay(self, partition: int = 1) -> None:
        await self.send_keys(await self._require_code() + "3", partition)

    async def disarm(self, partition: int = 1) -> None:
        await self.send_keys(await self._require_code() + "1", partition)

    async def bypass_zone(self, zone: int, partition: int = 1) -> None:
        await self.send_keys(await self._require_code() + f"6{zone:02d}", partition)

    async def toggle_chime(self, partition: int = 1) -> None:
        await self.send_keys(await self._require_code() + "9", partition)

    async def _poll_loop(self) -> None:
        """Keep the Envisalink watchdog alive and retrigger active alarms."""
        try:
            while not self._stop:
                await asyncio.sleep(30)
                try:
                    await self.poll()
                except Exception:  # noqa: BLE001
                    return
                if any(st == "alarm" for st in self.state.partitions.values()):
                    await notifier.notify(
                        tag="alarm",
                        title="ALARM",
                        body="Alarm is active on your security system.",
                        severity="alarm",
                        require_interaction=True,
                        cooldown=60,
                    )
        except asyncio.CancelledError:
            pass

    # --- inbound dispatch ---------------------------------------------------

    async def _dispatch(self, frame: str) -> None:
        sentinel = frame[0]
        body = frame[1:-1]
        cc, _, data = body.partition(",")
        cc = cc.upper()
        if sentinel == "^":
            code = p.decode_response_code(data)
            bus.publish({"type": "ack", "command": cc, "code": data, "message": code})
            return

        self.state.last_update = db.utcnow_iso()
        if cc == p.TPI_KEYPAD_UPDATE:
            await self._on_keypad(data)
        elif cc == p.TPI_ZONE_STATE_CHANGE:
            await self._on_zones(data)
        elif cc == p.TPI_PARTITION_STATE_CHANGE:
            await self._on_partitions(data)
        elif cc == p.TPI_CID_EVENT:
            await self._on_cid(data)
        elif cc == p.TPI_ZONE_TIMER_DUMP:
            await self._on_timers(data)

    async def _log(self, **kwargs) -> dict:
        ev = await db.insert_event(**kwargs)
        bus.publish({"type": "event", "event": ev})
        return ev

    def _publish_state(self) -> None:
        bus.publish({"type": "state", "state": self.state.to_dict()})

    async def _on_keypad(self, data: str) -> None:
        ku = p.parse_keypad_update(data)
        if ku is None:
            return
        ks = self.state.keypad(ku.partition)
        prev = dict(ks.led)
        ks.line1, ks.line2 = ku.line1, ku.line2
        ks.led = ku.led
        ks.beep = ku.beep
        ks.user_or_zone = ku.user_or_zone
        await self._eval_trouble(ku.partition, prev, ku.led)
        # Honeywell/Vista panels convey live partition status via the keypad LEDs,
        # not a periodic 02 command, so derive it here.
        await self._apply_partition_state(ku.partition, p.partition_state_from_leds(ku.led, ku.beep))
        self._publish_state()

    async def _eval_trouble(self, partition: int, prev: dict[str, bool], new: dict[str, bool]) -> None:
        edges = {
            "low_battery": ("Low Battery", "warning"),
            "trouble": ("System Trouble", "warning"),
            "fire": ("Fire", "alarm"),
        }
        for flag, (label, severity) in edges.items():
            if new.get(flag) and not prev.get(flag):
                await self._log(
                    event_type=flag, severity=severity, partition=partition,
                    status="active", detail=f"{label} condition reported",
                )
                await notifier.notify(
                    tag=flag, title=label, body=f"{label} on your security system.",
                    severity=severity, require_interaction=(severity == "alarm"),
                    cooldown=120,
                )
            elif prev.get(flag) and not new.get(flag):
                await self._log(
                    event_type=flag, severity="info", partition=partition,
                    status="restored", detail=f"{label} restored",
                )
        # AC power: present -> absent is a trouble condition.
        if prev.get("ac_present") and not new.get("ac_present"):
            await self._log(
                event_type="ac_trouble", severity="warning", partition=partition,
                status="active", detail="AC power lost (running on battery)",
            )
            await notifier.notify(
                tag="ac_trouble", title="AC Power Lost",
                body="The panel lost AC power and is on battery.",
                severity="warning", cooldown=300,
            )
        elif not prev.get("ac_present") and new.get("ac_present") and prev:
            await self._log(
                event_type="ac_trouble", severity="info", partition=partition,
                status="restored", detail="AC power restored",
            )

    async def _on_zones(self, data: str) -> None:
        new_open = p.parse_zone_bitfield(data)
        old_open = self.state.open_zones
        for z in sorted(new_open - old_open):
            await db.upsert_zone_seen(z)
            await self._log(event_type="zone_open", zone=z, status="open", detail=f"Zone {z} opened", raw=data)
        for z in sorted(old_open - new_open):
            await self._log(event_type="zone_restore", zone=z, status="closed", detail=f"Zone {z} closed")
        self.state.open_zones = new_open
        self._publish_state()

    async def _on_partitions(self, data: str) -> None:
        states = p.parse_partition_states(data)
        for part, st in states.items():
            # Ignore "not_used" from the 02 command for partitions the keypad
            # already reports, so it can't overwrite the derived live state.
            if st == "not_used" and part in self.state.partitions:
                continue
            await self._apply_partition_state(part, st)
        self._publish_state()

    async def _apply_partition_state(self, part: int, new: str) -> None:
        prev = self.state.partitions.get(part)
        if prev == new:
            return
        self.state.partitions[part] = new
        await self._on_partition_transition(part, prev, new)

    async def _on_partition_transition(self, part: int, prev: Optional[str], new: str) -> None:
        prev_armed = prev in ARMED_STATES
        new_armed = new in ARMED_STATES

        if new == "alarm" and prev != "alarm":
            await self._log(event_type="alarm", severity="alarm", partition=part, status="alarm",
                            detail=f"Partition {part} in ALARM")
            await notifier.notify(
                tag="alarm", title="ALARM TRIGGERED",
                body=f"Partition {part} is in alarm.",
                severity="alarm", require_interaction=True, cooldown=60,
            )
        elif prev == "alarm" and new != "alarm":
            await self._log(event_type="alarm", severity="info", partition=part, status="cleared",
                            detail=f"Partition {part} alarm cleared")

        if new_armed and not prev_armed:
            etype = "arm_away" if new in ("armed_away", "armed_max") else "arm_stay"
            label = "Armed Away" if etype == "arm_away" else "Armed Stay"
            await self._log(event_type=etype, severity="info", partition=part, status=new, detail=label)
            await notifier.notify(tag=f"arm_{part}", title=label,
                                  body=f"Partition {part} {label.lower()}.", severity="info")
        elif prev_armed and not new_armed and new not in ("alarm", "alarm_in_memory"):
            await self._log(event_type="disarm", severity="info", partition=part, status=new, detail="Disarmed")
            await notifier.notify(tag=f"arm_{part}", title="Disarmed",
                                  body=f"Partition {part} disarmed.", severity="info")

    async def _on_cid(self, data: str) -> None:
        ev = p.parse_cid_event(data)
        if ev is None:
            return
        event_type, severity, should_push = classify_cid(ev)
        # For alarm codes the CID carries the triggering zone.
        zone = ev.zone_or_user if event_type in ("alarm", "trouble", "low_battery") else None
        user = ev.zone_or_user if event_type == "arm_disarm" else None
        detail = f"CID {'restore' if ev.is_restore else 'event'} {ev.code:03d} (partition {ev.partition})"
        await self._log(event_type=f"cid_{event_type}", severity=severity, partition=ev.partition,
                        zone=zone, user_num=user, status="restore" if ev.is_restore else "event",
                        detail=detail, raw=ev.raw)
        if should_push:
            await notifier.notify(
                tag="alarm" if severity == "alarm" else event_type,
                title="ALARM" if severity == "alarm" else event_type.replace("_", " ").title(),
                body=detail, severity=severity,
                require_interaction=(severity == "alarm"), cooldown=60,
            )

    async def _on_timers(self, data: str) -> None:
        self.state.zone_timers = p.parse_zone_timers(data)
        for z in self.state.zone_timers:
            await db.upsert_zone_seen(z)
        self._publish_state()


client = TpiClient()
