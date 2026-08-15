import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useStore } from "../lib/store";
import { ZoneIcon, ZONE_TYPE_LABELS } from "../components/ZoneIcon";
import { formatDuration } from "../lib/format";
import type { ZoneRow } from "../lib/types";

const TYPE_KEYS = Object.keys(ZONE_TYPE_LABELS);

export function Zones() {
  const zones = useStore((s) => s.zones);
  const setZones = useStore((s) => s.setZones);
  const openZones = useStore((s) => s.panel?.open_zones ?? []);
  const [editing, setEditing] = useState<ZoneRow | null>(null);

  const load = () => api.zones.list().then(setZones).catch(() => undefined);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const merged = zones.map((z) => ({ ...z, open: openZones.includes(z.number) }));

  return (
    <>
      <div className="section-title">
        <h2>Zones</h2>
        <span className="mono dim" style={{ fontSize: 12 }}>{merged.length} known</span>
      </div>

      {merged.length === 0 ? (
        <div className="card dim" style={{ fontSize: 13 }}>
          No zones seen yet. Zones appear here automatically the first time the panel reports
          activity on them (open a door, trip a sensor, or run a zone-timer dump).
        </div>
      ) : (
        <div className="stack">
          {merged.map((z) => (
            <div
              key={z.number}
              className={`zone-item ${z.open ? "open" : ""} ${z.configured ? "" : "unconfigured"}`}
              onClick={() => setEditing(z)}
            >
              <div className="zone-icon-wrap">
                <ZoneIcon type={z.zone_type} />
              </div>
              <div className="stack" style={{ gap: 2 }}>
                <span style={{ fontWeight: 600 }}>
                  {z.name || `Zone ${z.number} — Unnamed`}
                </span>
                <span className="zone-num">
                  ZONE {String(z.number).padStart(2, "0")}
                  {z.zone_type ? ` · ${ZONE_TYPE_LABELS[z.zone_type] ?? z.zone_type}` : ""}
                </span>
              </div>
              <span className="spacer" />
              {z.open ? (
                <span className="pill pill-warn">Open</span>
              ) : z.seconds_since_seen != null ? (
                <span className="pill pill-dim">{formatDuration(z.seconds_since_seen)} ago</span>
              ) : (
                <span className="pill pill-ok">Closed</span>
              )}
            </div>
          ))}
        </div>
      )}

      {editing && (
        <ZoneEditor
          zone={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            load();
          }}
        />
      )}
    </>
  );
}

function ZoneEditor({
  zone,
  onClose,
  onSaved,
}: {
  zone: ZoneRow;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(zone.name ?? "");
  const [type, setType] = useState(zone.zone_type ?? "generic");
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    try {
      await api.zones.save(zone.number, { name: name.trim() || null, zone_type: type, icon: null });
      onSaved();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-handle" />
        <div className="row between" style={{ marginBottom: 14 }}>
          <h2 style={{ fontSize: 18 }}>Configure zone</h2>
          <span className="mono dim">ZONE {String(zone.number).padStart(2, "0")}</span>
        </div>

        <div className="field">
          <label>Name</label>
          <input
            className="input"
            placeholder="e.g. Front Door"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
        </div>

        <div className="field">
          <label>Type &amp; icon</label>
          <div className="type-grid">
            {TYPE_KEYS.map((key) => (
              <div
                key={key}
                className={`type-chip ${type === key ? "selected" : ""}`}
                onClick={() => setType(key)}
              >
                <ZoneIcon type={key} size={20} />
                {ZONE_TYPE_LABELS[key]}
              </div>
            ))}
          </div>
        </div>

        <button className="btn btn-primary btn-block btn-lg" disabled={busy} onClick={save}>
          {busy ? "Saving…" : "Save zone"}
        </button>
      </div>
    </div>
  );
}
