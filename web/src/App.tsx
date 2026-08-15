import { useEffect } from "react";
import { Route, Routes } from "react-router-dom";
import { useAuth } from "./lib/auth";
import { connectWs, disconnectWs } from "./lib/ws";
import { Layout } from "./components/Layout";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Zones } from "./pages/Zones";
import { Keypad } from "./pages/Keypad";
import { Log } from "./pages/Log";
import { Settings } from "./pages/Settings";

export default function App() {
  const { loading, authenticated } = useAuth();

  useEffect(() => {
    if (authenticated) {
      connectWs();
      return () => disconnectWs();
    }
  }, [authenticated]);

  if (loading) {
    return (
      <div className="center-screen">
        <span className="dim mono">loading…</span>
      </div>
    );
  }

  if (!authenticated) return <Login />;

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/zones" element={<Zones />} />
        <Route path="/keypad" element={<Keypad />} />
        <Route path="/log" element={<Log />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="*" element={<Dashboard />} />
      </Routes>
    </Layout>
  );
}
