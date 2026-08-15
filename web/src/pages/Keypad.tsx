import { useState } from "react";
import { Lock, Home, LockOpen } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useStore } from "../lib/store";

const DIGITS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"];
const FN_KEYS = ["A", "B", "C", "D"];

export function Keypad() {
  const panel = useStore((s) => s.panel);
  const [error, setError] = useState<string | null>(null);
  const connected = panel?.logged_in ?? false;

  const dp = String(panel?.default_partition ?? 1);
  const kp = panel?.partitions[dp]?.keypad;
  const line1 = (kp?.line1 ?? "").padEnd(16, " ");
  const line2 = (kp?.line2 ?? "").padEnd(16, " ");

  async function run(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Command failed.");
    }
  }

  const press = (key: string) => run(() => api.panel.keypress(key));

  return (
    <>
      <div className="section-title">
        <h2>Keypad</h2>
        <span className="mono dim" style={{ fontSize: 12 }}>PARTITION {dp}</span>
      </div>

      <div className="keypad-display">
        {connected ? `${line1}\n${line2}` : "  -- OFFLINE --  \n                "}
      </div>

      {error && <div className="toast-error" style={{ margin: "10px 2px" }}>{error}</div>}

      <div className="key-grid">
        {DIGITS.map((d) => (
          <button key={d} className="key" disabled={!connected} onClick={() => press(d)}>
            {d}
          </button>
        ))}
      </div>

      <div className="fn-grid">
        {FN_KEYS.map((k) => (
          <button key={k} className="fn-key" disabled={!connected} onClick={() => press(k)}>
            {k}
          </button>
        ))}
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <div className="card-title">Quick actions</div>
        <div className="grid-2">
          <button className="btn btn-primary" disabled={!connected} onClick={() => run(() => api.panel.armAway())}>
            <Lock size={16} /> Arm Away
          </button>
          <button className="btn btn-ok" disabled={!connected} onClick={() => run(() => api.panel.armStay())}>
            <Home size={16} /> Arm Stay
          </button>
        </div>
        <button
          className="btn btn-danger btn-block"
          style={{ marginTop: 10 }}
          disabled={!connected}
          onClick={() => run(() => api.panel.disarm())}
        >
          <LockOpen size={16} /> Disarm
        </button>
      </div>

      <div className="note info" style={{ marginTop: 14 }}>
        Buttons send real keystrokes to the panel over the TPI link — this behaves like a physical
        keypad, not a simulation.
      </div>
    </>
  );
}
