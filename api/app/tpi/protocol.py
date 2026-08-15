"""EnvisaLink Vista TPI protocol definitions and parsers.

Source of truth: EnvisaLink Vista TPI Programmer's Document v1.03 (Honeywell/Ademco
firmware). This module targets the Envisalink 4 (128 zones).

Packet framing:
    From Envisalink:  %CC,DATA$
    To Envisalink:    ^CC,DATA$   (escaped command), ack: ^CC,EE$
                      raw keystrokes for <0-9,#,*> go straight through.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# --- Application commands sent TO the Envisalink (2-digit hex codes) ---------
CMD_POLL = "00"
CMD_CHANGE_DEFAULT_PARTITION = "01"
CMD_DUMP_ZONE_TIMERS = "02"
CMD_KEYPRESS_PARTITION = "03"

# --- TPI commands received FROM the Envisalink ------------------------------
TPI_KEYPAD_UPDATE = "00"
TPI_ZONE_STATE_CHANGE = "01"
TPI_PARTITION_STATE_CHANGE = "02"
TPI_CID_EVENT = "03"
TPI_ZONE_TIMER_DUMP = "FF"

# --- TPI response codes (EE in ^CC,EE$) -------------------------------------
RESPONSE_CODES = {
    "00": "No Error - Command Accepted",
    "01": "Receive Buffer Overrun",
    "02": "Unknown Command",
    "03": "Syntax Error",
    "04": "Receive Buffer Overflow",
    "05": "Receive State Machine Timeout",
    # Single-digit forms also appear in practice.
    "0": "No Error - Command Accepted",
    "1": "Receive Buffer Overrun",
    "2": "Unknown Command",
    "3": "Syntax Error",
    "4": "Receive Buffer Overflow",
    "5": "Receive State Machine Timeout",
}

# --- LED / ICON bitfield (16-bit hex in keypad update) ----------------------
LED_BITS = {
    15: "armed_stay",
    14: "low_battery",
    13: "fire",
    12: "ready",
    9: "trouble",          # CHECK ICON - SYSTEM TROUBLE
    8: "fire_alarm",       # ALARM (FIRE ZONE)
    7: "armed_zero_entry",
    5: "chime",
    4: "bypass",
    3: "ac_present",
    2: "armed_away",
    1: "alarm_in_memory",
    0: "alarm",            # System is in Alarm
}

# --- Partition status codes (02 command) ------------------------------------
PARTITION_STATES = {
    0: "not_used",
    1: "ready",
    2: "ready_bypass",     # Ready to Arm (zones bypassed)
    3: "not_ready",
    4: "armed_stay",
    5: "armed_away",
    6: "armed_instant",    # zero entry delay - stay
    7: "exit_delay",
    8: "alarm",
    9: "alarm_in_memory",
    10: "armed_max",       # zero entry delay - away
}

ARMED_STATES = {"armed_stay", "armed_away", "armed_instant", "armed_max"}


def partition_state_from_leds(led: dict[str, bool], beep: str = "off") -> str:
    """Derive an abstracted partition state from a keypad LED bitfield.

    Honeywell/Vista firmware reports live status primarily through the periodic
    Virtual Keypad Update (command 00) LED flags, not the 02 partition command,
    so this is the primary state source for those panels.
    """
    zero_entry = led.get("armed_zero_entry", False)
    if led.get("alarm"):
        return "alarm"
    if led.get("armed_away"):
        return "armed_max" if zero_entry else "armed_away"
    if led.get("armed_stay"):
        return "armed_instant" if zero_entry else "armed_stay"
    if zero_entry:
        return "armed_instant"
    if beep == "continuous_slow":  # exit delay beep
        return "exit_delay"
    if led.get("ready"):
        return "ready_bypass" if led.get("bypass") else "ready"
    if led.get("alarm_in_memory"):
        return "alarm_in_memory"
    return "not_ready"


# --- Beep field -------------------------------------------------------------
BEEP_STATES = {
    0: "off",
    1: "beep_1",
    2: "beep_2",
    3: "beep_3",
    4: "continuous_fast",  # trouble / urgency
    5: "continuous_slow",  # exit delay
}


def decode_response_code(code: str) -> str:
    return RESPONSE_CODES.get(code.strip(), f"Unknown response ({code})")


def decode_led_bitfield(hex_str: str) -> dict[str, bool]:
    """Decode the 2-byte hex LED/ICON bitfield into named flags."""
    try:
        value = int(hex_str, 16)
    except ValueError:
        value = 0
    return {name: bool(value & (1 << bit)) for bit, name in LED_BITS.items()}


@dataclass
class KeypadUpdate:
    partition: int
    led: dict[str, bool]
    led_raw: str
    user_or_zone: int
    beep: str
    line1: str
    line2: str

    @property
    def alpha(self) -> str:
        return (self.line1 + self.line2).rstrip()


def parse_keypad_update(data: str) -> Optional[KeypadUpdate]:
    """Parse TPI 00: partition,ledhex,user/zone,beep,alpha(32 chars).

    The alpha field itself may contain commas, so split with a max count.
    """
    parts = data.split(",", 4)
    if len(parts) < 5:
        return None
    try:
        partition = int(parts[0])
        led_raw = parts[1]
        user_or_zone = int(parts[2], 16)
        beep = BEEP_STATES.get(int(parts[3], 16) if parts[3] else 0, "off")
    except ValueError:
        return None
    alpha = parts[4]
    line1 = alpha[:16]
    line2 = alpha[16:32]
    return KeypadUpdate(
        partition=partition,
        led=decode_led_bitfield(led_raw),
        led_raw=led_raw,
        user_or_zone=user_or_zone,
        beep=beep,
        line1=line1,
        line2=line2,
    )


def parse_zone_bitfield(data: str) -> set[int]:
    """Decode TPI 01 zone state change.

    A packed hex string; the *string* is little-endian by byte, but each byte is
    big-endian (MSbit on the left). Bit N (0-based) set => zone N+1 open/faulted.
    """
    open_zones: set[int] = set()
    data = data.strip()
    # Each byte = 2 hex chars, processed in order (little-endian byte 0 first).
    for byte_index in range(len(data) // 2):
        chunk = data[byte_index * 2 : byte_index * 2 + 2]
        try:
            byte_val = int(chunk, 16)
        except ValueError:
            continue
        for bit in range(8):
            if byte_val & (1 << bit):
                zone = byte_index * 8 + bit + 1
                open_zones.add(zone)
    return open_zones


def parse_partition_states(data: str) -> dict[int, str]:
    """Decode TPI 02: one status byte per partition, partition 1 first."""
    states: dict[int, str] = {}
    data = data.strip()
    for i in range(len(data) // 2):
        chunk = data[i * 2 : i * 2 + 2]
        try:
            code = int(chunk, 16)
        except ValueError:
            continue
        states[i + 1] = PARTITION_STATES.get(code, f"unknown_{code}")
    return states


@dataclass
class CidEvent:
    qualifier: int           # 1 = event, 3 = restore
    code: int                # 3-digit ContactID code
    partition: int
    zone_or_user: int
    raw: str
    is_restore: bool = field(init=False)

    def __post_init__(self) -> None:
        self.is_restore = self.qualifier == 3


def parse_cid_event(data: str) -> Optional[CidEvent]:
    """Decode TPI 03: QXXXPPZZZ0 (BCD ASCII, 10 digits)."""
    data = data.strip()
    if len(data) < 10 or not data.isdigit():
        return None
    return CidEvent(
        qualifier=int(data[0]),
        code=int(data[1:4]),
        partition=int(data[4:6]),
        zone_or_user=int(data[6:9]),
        raw=data,
    )


def parse_zone_timers(data: str) -> dict[int, int]:
    """Decode TPI FF: 128 little-endian UINT16 zone timers (1 tick = 5 s).

    0xFFFF => just opened; 0x0000 => closed long ago. Returns {zone: seconds_since_seen}
    for zones that have a non-zero timer.
    """
    timers: dict[int, int] = {}
    data = data.strip()
    for i in range(len(data) // 4):
        word = data[i * 4 : i * 4 + 4]
        try:
            low = int(word[0:2], 16)
            high = int(word[2:4], 16)
        except ValueError:
            continue
        value = low | (high << 8)  # little-endian
        if value:
            # Seconds since the zone was last seen open (each tick = 5 s from 0xFFFF).
            timers[i + 1] = (0xFFFF - value) * 5
    return timers
