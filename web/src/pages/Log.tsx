import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import { useStore } from "../lib/store";
import { formatDateTime, titleCase } from "../lib/format";
import type { EventRow } from "../lib/types";

const EVENT_TYPES = [
  "",
  "zone_open",
  "zone_restore",
  "arm_away",
  "arm_stay",
  "disarm",
  "alarm",
  "low_battery",
  "trouble",
  "ac_trouble",
  "fire",
  "cid_alarm",
  "cid_trouble",
  "connected",
];

const PAGE_SIZE = 50;

function toIso(local: string): string | undefined {
  if (!local) return undefined;
  const d = new Date(local);
  return isNaN(d.getTime()) ? undefined : d.toISOString();
}

export function Log() {
  const zones = useStore((s) => s.zones);
  const liveEvents = useStore((s) => s.liveEvents);
  const [zone, setZone] = useState("");
  const [eventType, setEventType] = useState("");
  const [severity, setSeverity] = useState("");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [offset, setOffset] = useState(0);

  const [rows, setRows] = useState<EventRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const zoneName = (n: number | null) =>
    n == null ? null : zones.find((z) => z.number === n)?.name || `Zone ${n}`;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.events.list({
        zone: zone || undefined,
        event_type: eventType || undefined,
        severity: severity || undefined,
        since: toIso(since),
        until: toIso(until),
        limit: PAGE_SIZE,
        offset,
      });
      setRows(res.events);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [zone, eventType, severity, since, until, offset]);

  useEffect(() => {
    load();
  }, [load]);

  // Refresh page 1 automatically when new live events arrive.
  useEffect(() => {
    if (offset === 0) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [liveEvents.length]);

  const resetAnd = (fn: () => void) => {
    setOffset(0);
    fn();
  };

  return (
    <>
      <div className="section-title">
        <h2>Event log</h2>
        <button className="btn" style={{ padding: "6px 10px" }} onClick={load}>
          <RefreshCw size={14} className={loading ? "spin" : ""} />
        </button>
      </div>

      <div className="card">
        <div className="filter-bar">
          <div className="field">
            <label>Zone #</label>
            <input
              className="input mono"
              inputMode="numeric"
              placeholder="any"
              value={zone}
              onChange={(e) => resetAnd(() => setZone(e.target.value.replace(/\D/g, "")))}
            />
          </div>
          <div className="field">
            <label>Type</label>
            <select className="select" value={eventType} onChange={(e) => resetAnd(() => setEventType(e.target.value))}>
              {EVENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t === "" ? "All types" : titleCase(t)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Severity</label>
            <select className="select" value={severity} onChange={(e) => resetAnd(() => setSeverity(e.target.value))}>
              <option value="">All</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="alarm">Alarm</option>
            </select>
          </div>
          <div className="field">
            <label>From</label>
            <input className="input" type="datetime-local" value={since} onChange={(e) => resetAnd(() => setSince(e.target.value))} />
          </div>
          <div className="field">
            <label>To</label>
            <input className="input" type="datetime-local" value={until} onChange={(e) => resetAnd(() => setUntil(e.target.value))} />
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        {rows.length === 0 ? (
          <div className="dim" style={{ fontSize: 13 }}>No events match these filters.</div>
        ) : (
          <div className="event-list">
            {rows.map((ev) => (
              <div key={ev.id} className="event-row">
                <span className={`sev-bar ${ev.severity}`} />
                <div className="stack" style={{ gap: 3 }}>
                  <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                    <span className="event-type">{ev.event_type}</span>
                    {ev.zone != null && <span className="pill pill-dim">{zoneName(ev.zone)}</span>}
                    {ev.partition != null && <span className="mono dim" style={{ fontSize: 11 }}>P{ev.partition}</span>}
                  </div>
                  <span className="muted" style={{ fontSize: 13 }}>{ev.detail}</span>
                  {ev.raw && <span className="mono dim" style={{ fontSize: 10 }}>{ev.raw}</span>}
                </div>
                <span className="event-meta">{formatDateTime(ev.ts)}</span>
              </div>
            ))}
          </div>
        )}

        <div className="pagination">
          <span className="dim" style={{ fontSize: 12 }}>
            {total === 0 ? "0" : `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)}`} of {total}
          </span>
          <div className="row" style={{ gap: 8 }}>
            <button className="btn" style={{ padding: "8px 12px" }} disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
              Prev
            </button>
            <button
              className="btn"
              style={{ padding: "8px 12px" }}
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
