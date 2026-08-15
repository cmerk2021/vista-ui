import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";

export function Login() {
  const { setupComplete, refresh } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isSetup = !setupComplete;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (isSetup && password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (isSetup && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      if (isSetup) await api.auth.setup(password);
      else await api.auth.login(password);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center-screen">
      <form className="card" style={{ width: "100%", maxWidth: 380 }} onSubmit={submit}>
        <div className="row" style={{ gap: 12, marginBottom: 8 }}>
          <ShieldCheck size={28} color="var(--accent)" />
          <div>
            <h1 style={{ fontSize: 20 }}>Vista Security</h1>
            <div className="dim" style={{ fontSize: 13 }}>
              {isSetup ? "First-run setup — create a password" : "Enter your password"}
            </div>
          </div>
        </div>

        <div className="field">
          <label>Password</label>
          <input
            className="input"
            type="password"
            autoComplete={isSetup ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
          />
        </div>

        {isSetup && (
          <div className="field">
            <label>Confirm password</label>
            <input
              className="input"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>
        )}

        {error && <div className="toast-error" style={{ marginBottom: 12 }}>{error}</div>}

        <button className="btn btn-primary btn-block btn-lg" disabled={busy}>
          {busy ? "…" : isSetup ? "Create & continue" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
