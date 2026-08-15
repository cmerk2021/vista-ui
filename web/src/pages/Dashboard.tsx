import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Lock, ShieldCheck, Home, LockOpen, TriangleAlert, ChevronRight } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useStore } from "../lib/store";
import { statusMeta, troubleFlags, ARMED_STATES } from "../lib/panel";
import { pillClass, formatTime, titleCase } from "../lib/format";
import { ZoneIcon } from "../components/ZoneIcon";

export function Dashboard() {
  const panel = useStore((s) => s.panel);
  const wsConnected = useStore((s) => s.wsConnected);
  const zones = useStore((s) => s.zones);
  const setZones = useStore((s) => s.setZones);
  const liveEvents = useStore((s) => s.liveEvents);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.zones.list().then(setZones).catch(() => undefined);
  }, [setZones]);

  const dp = String(panel?.default_partition ?? 1);
  const part = panel?.partitions[dp];
  const meta = statusMeta(part?.state);
  const linkUp = wsConnected && (panel?.logged_in ?? false);
  const connected = linkUp;
  const reconnecting = !linkUp && !!part;
  const armed = ARMED_STATES.has(part?.state ?? "");
  const inAlarm = part?.state === "alarm" || part?.keypad.led?.alarm;

  const openZones = panel?.open_zones ?? [];
  const troubles = troubleFlags(part?.keypad.led);
  const notReady = part?.state === "not_ready" || part?.state === "ready_bypass";
  const hasFaults = openZones.length > 0 || troubles.length > 0;

  const zoneName = (n: number) => zones.find((z) => z.number === n)?.name || `Zone ${n}`;
  const zoneType = (n: number) => zones.find((z) => z.number === n)?.zone_type ?? "generic";

  async function run(action: () => Promise<unknown>) {
    setError(null);
    setBusy(true);
    try {
      await action();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Command failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {/* Status hero */}
      <div className={`card status-hero tone-${meta.tone} ${inAlarm ? "pulsing" : ""}`}>
        <div className="row between">
          <span className={pillClass(meta.tone)}>Partition {dp}</span>
          <span className="mono dim" style={{ fontSize: 11 }}>
            {reconnecting ? "reconnecting…" : panel?.last_update ? formatTime(panel.last_update) : "—"}
          </span>
        </div>
        <div className="status-label">{part ? meta.label : linkUp ? "Waiting…" : "Offline"}</div>
        <div className="muted">
          {!linkUp
            ? part
              ? "Reconnecting to the panel…"
              : "Not connected to the Envisalink"
            : meta.hint}
        </div>
        {part?.keypad.line1 ? (
          <div className="keypad-strip mono">
            <div>{part.keypad.line1.trimEnd()}</div>
            <div>{part.keypad.line2.trimEnd()}</div>
          </div>
        ) : null}
      </div>

      {/* Faulted zones — the most useful part when not ready */}
      {(notReady || hasFaults) && !armed && (
        <div className="card">
          <div className="card-title" style={{ color: "var(--warn)" }}>
            <TriangleAlert size={13} style={{ verticalAlign: -2, marginRight: 6 }} />
            Not ready to arm — {openZones.length + troubles.length} item(s)
          </div>
          <div className="stack">
            {openZones.map((n) => (
              <div key={n} className="fault-row">
                <ZoneIcon type={zoneType(n)} />
                <div className="stack" style={{ gap: 0 }}>
                  <span>{zoneName(n)}</span>
                  <span className="mono dim" style={{ fontSize: 11 }}>
                    ZONE {String(n).padStart(2, "0")}
                  </span>
                </div>
                <span className="spacer" />
                <span className="pill pill-warn">Open</span>
                <button
                  className="btn"
                  style={{ padding: "6px 10px", fontSize: 12 }}
                  disabled={busy || !connected}
                  onClick={() => run(() => api.panel.bypass(n))}
                >
                  Bypass
                </button>
              </div>
            ))}
            {troubles.map((t) => (
              <div key={t} className="fault-row">
                <TriangleAlert size={20} color="var(--warn)" />
                <span>{t}</span>
                <span className="spacer" />
                <span className="pill pill-warn">Trouble</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="card">
        <div className="card-title">Controls</div>
        {error && <div className="toast-error" style={{ marginBottom: 12 }}>{error}</div>}
        {!armed ? (
          <div className="grid-2">
            <button
              className="btn btn-primary btn-lg"
              disabled={busy || !connected}
              onClick={() => run(() => api.panel.armAway())}
            >
              <Lock size={18} /> Arm Away
            </button>
            <button
              className="btn btn-ok btn-lg"
              disabled={busy || !connected}
              onClick={() => run(() => api.panel.armStay())}
            >
              <Home size={18} /> Arm Stay
            </button>
          </div>
        ) : (
          <div className="armed-panel">
            <ShieldCheck size={22} color="var(--accent)" />
            <span>System is {meta.label.toLowerCase()}.</span>
          </div>
        )}
        {(armed || inAlarm) && (
          <button
            className="btn btn-danger btn-lg btn-block"
            style={{ marginTop: 12 }}
            disabled={busy || !connected}
            onClick={() => run(() => api.panel.disarm())}
          >
            <LockOpen size={18} /> Disarm
          </button>
        )}
      </div>

      {/* Recent activity */}
      <div className="section-title">
        <h2>Recent activity</h2>
        <Link to="/log" className="row dim" style={{ fontSize: 13 }}>
          View log <ChevronRight size={15} />
        </Link>
      </div>
      <div className="card">
        {liveEvents.length === 0 ? (
          <div className="dim" style={{ fontSize: 13 }}>No events yet this session.</div>
        ) : (
          <div className="stack">
            {liveEvents.slice(0, 6).map((ev) => (
              <div key={ev.id} className="row between">
                <div className="row" style={{ gap: 10 }}>
                  <span className={pillClass(ev.severity === "alarm" ? "alarm" : ev.severity === "warning" ? "warn" : "idle")}>
                    {titleCase(ev.event_type)}
                  </span>
                  <span className="muted" style={{ fontSize: 13 }}>{ev.detail}</span>
                </div>
                <span className="mono dim" style={{ fontSize: 11 }}>{formatTime(ev.ts)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
