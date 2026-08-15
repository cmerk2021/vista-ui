import { useEffect, useState } from "react";
import { BellRing, LogOut, Plug, RefreshCw } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useStore } from "../lib/store";
import { pushSupported, subscribeToPush, unsubscribeFromPush, currentSubscription } from "../lib/push";
import { ZONE_TYPE_LABELS } from "../components/ZoneIcon";
import type { ConnectionConfig, NotificationPrefs } from "../lib/types";

export function Settings() {
  const { logout } = useAuth();
  const zones = useStore((s) => s.zones);
  const setZones = useStore((s) => s.setZones);

  useEffect(() => {
    api.zones.list().then(setZones).catch(() => undefined);
  }, [setZones]);

  return (
    <>
      <div className="section-title">
        <h2>Settings</h2>
      </div>
      <ConnectionCard />
      <NotificationsCard />
      <PasswordCard />

      <div className="card">
        <div className="card-title">Configured zones</div>
        {zones.filter((z) => z.name).length === 0 ? (
          <div className="dim" style={{ fontSize: 13 }}>No zones named yet — configure them on the Zones page.</div>
        ) : (
          <table className="summary-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Name</th>
                <th>Type</th>
              </tr>
            </thead>
            <tbody>
              {zones
                .filter((z) => z.name)
                .map((z) => (
                  <tr key={z.number}>
                    <td className="mono">{String(z.number).padStart(2, "0")}</td>
                    <td>{z.name}</td>
                    <td className="muted">{ZONE_TYPE_LABELS[z.zone_type ?? "generic"] ?? z.zone_type}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </div>

      <button className="btn btn-block" style={{ marginTop: 14 }} onClick={() => logout()}>
        <LogOut size={16} /> Sign out
      </button>
    </>
  );
}

function ConnectionCard() {
  const [cfg, setCfg] = useState<ConnectionConfig | null>(null);
  const [host, setHost] = useState("");
  const [port, setPort] = useState("4025");
  const [password, setPassword] = useState("");
  const [userCode, setUserCode] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () =>
    api.settings.getConnection().then((c) => {
      setCfg(c);
      setHost(c.host);
      setPort(String(c.port));
    });

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      const body: Record<string, unknown> = { host, port: Number(port) };
      if (password) body.password = password;
      if (userCode) body.user_code = userCode;
      await api.settings.setConnection(body);
      setPassword("");
      setUserCode("");
      setMsg("Saved. Reconnecting to the Envisalink…");
      await load();
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="row between" style={{ marginBottom: 12 }}>
        <div className="card-title" style={{ margin: 0 }}>
          <Plug size={13} style={{ verticalAlign: -2, marginRight: 6 }} />
          Envisalink connection
        </div>
        <span className={`pill ${cfg?.logged_in ? "pill-ok" : "pill-alarm"}`}>
          {cfg?.logged_in ? "Linked" : cfg?.connected ? "No login" : "Offline"}
        </span>
      </div>

      <div className="grid-2">
        <div className="field">
          <label>Host / IP</label>
          <input className="input mono" value={host} onChange={(e) => setHost(e.target.value)} />
        </div>
        <div className="field">
          <label>Port</label>
          <input className="input mono" inputMode="numeric" value={port} onChange={(e) => setPort(e.target.value.replace(/\D/g, ""))} />
        </div>
      </div>
      <div className="field">
        <label>TPI password {cfg?.password_set && <span className="dim">· set</span>}</label>
        <input
          className="input"
          type="password"
          placeholder={cfg?.password_set ? "•••••••• (unchanged)" : "Envisalink password"}
          maxLength={10}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>
      <div className="field">
        <label>Panel user code {cfg?.user_code_set && <span className="dim">· set</span>}</label>
        <input
          className="input mono"
          type="password"
          inputMode="numeric"
          placeholder={cfg?.user_code_set ? "•••• (unchanged)" : "4–6 digit code"}
          maxLength={6}
          value={userCode}
          onChange={(e) => setUserCode(e.target.value.replace(/\D/g, ""))}
        />
        <span className="dim" style={{ fontSize: 11 }}>
          Stored encrypted. Used to build arm/disarm keystrokes (code+2 away, +3 stay, +1 disarm).
        </span>
      </div>

      {msg && <div className="muted" style={{ fontSize: 13, marginBottom: 10 }}>{msg}</div>}
      <button className="btn btn-primary btn-block" disabled={busy} onClick={save}>
        {busy ? "Saving…" : "Save connection"}
      </button>
    </div>
  );
}

function NotificationsCard() {
  const [supported] = useState(pushSupported());
  const [subscribed, setSubscribed] = useState(false);
  const [prefs, setPrefs] = useState<NotificationPrefs>({ arm_disarm: true, alarms: true, troubles: true });
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    currentSubscription().then((s) => setSubscribed(!!s));
    api.settings.getNotifications().then(setPrefs).catch(() => undefined);
  }, []);

  async function toggleSub() {
    setBusy(true);
    setMsg(null);
    try {
      if (subscribed) {
        await unsubscribeFromPush();
        setSubscribed(false);
      } else {
        await subscribeToPush();
        setSubscribed(true);
      }
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Failed.");
    } finally {
      setBusy(false);
    }
  }

  async function setPref(key: keyof NotificationPrefs, value: boolean) {
    const next = { ...prefs, [key]: value };
    setPrefs(next);
    await api.settings.setNotifications(next).catch(() => undefined);
  }

  return (
    <div className="card">
      <div className="card-title">
        <BellRing size={13} style={{ verticalAlign: -2, marginRight: 6 }} />
        Notifications
      </div>

      {!supported ? (
        <div className="note">
          This browser doesn't support Web Push. On iOS you must first add this app to your Home
          Screen (Share → Add to Home Screen) and open it from there.
        </div>
      ) : (
        <>
          <button className="btn btn-block" disabled={busy} onClick={toggleSub}>
            {busy ? "…" : subscribed ? "Disable push on this device" : "Enable push on this device"}
          </button>
          {subscribed && (
            <button
              className="btn btn-block"
              style={{ marginTop: 8 }}
              onClick={() => api.push.test().then(() => setMsg("Test sent.")).catch(() => setMsg("Test failed."))}
            >
              <RefreshCw size={14} /> Send test notification
            </button>
          )}
          {msg && <div className="muted" style={{ fontSize: 13, marginTop: 8 }}>{msg}</div>}

          <div style={{ marginTop: 14 }}>
            <PrefRow label="Arm / disarm" desc="Away, stay, disarm state changes" value={prefs.arm_disarm} onChange={(v) => setPref("arm_disarm", v)} />
            <PrefRow label="Alarms" desc="Any alarm trip — highest priority" value={prefs.alarms} onChange={(v) => setPref("alarms", v)} />
            <PrefRow label="Trouble / faults" desc="Low battery, AC loss, zone trouble" value={prefs.troubles} onChange={(v) => setPref("troubles", v)} />
          </div>

          <div className="note" style={{ marginTop: 14 }}>
            <strong>Honest limitation:</strong> alarm pushes use every attention-grabbing option Web
            Push allows (persistent banner, vibration, urgent styling). They still cannot bypass iOS
            Do Not Disturb / Focus — Apple restricts true critical alerts to native apps only.
          </div>
        </>
      )}
    </div>
  );
}

function PrefRow({
  label,
  desc,
  value,
  onChange,
}: {
  label: string;
  desc: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="setting-row">
      <div className="stack" style={{ gap: 2 }}>
        <span style={{ fontWeight: 600 }}>{label}</span>
        <span className="dim" style={{ fontSize: 12 }}>{desc}</span>
      </div>
      <div className={`toggle ${value ? "on" : ""}`} onClick={() => onChange(!value)} />
    </div>
  );
}

function PasswordCard() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    setMsg(null);
    try {
      await api.settings.changePassword(current, next);
      setCurrent("");
      setNext("");
      setMsg("Password changed.");
    } catch (err) {
      setMsg(err instanceof ApiError ? err.message : "Failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="card-title">App password</div>
      <div className="field">
        <label>Current password</label>
        <input className="input" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} />
      </div>
      <div className="field">
        <label>New password</label>
        <input className="input" type="password" value={next} onChange={(e) => setNext(e.target.value)} />
      </div>
      {msg && <div className="muted" style={{ fontSize: 13, marginBottom: 10 }}>{msg}</div>}
      <button className="btn btn-block" disabled={busy || !current || next.length < 8} onClick={save}>
        {busy ? "…" : "Change password"}
      </button>
    </div>
  );
}
