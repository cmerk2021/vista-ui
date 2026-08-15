export type Tone = "ok" | "warn" | "alarm" | "armed" | "idle";

interface StatusMeta {
  label: string;
  tone: Tone;
  hint: string;
}

const STATUS: Record<string, StatusMeta> = {
  ready: { label: "Ready", tone: "ok", hint: "All zones secure" },
  ready_bypass: { label: "Ready (Bypass)", tone: "warn", hint: "Zones bypassed" },
  not_ready: { label: "Not Ready", tone: "warn", hint: "Zones faulted" },
  armed_stay: { label: "Armed Stay", tone: "armed", hint: "Perimeter armed" },
  armed_away: { label: "Armed Away", tone: "armed", hint: "Fully armed" },
  armed_instant: { label: "Armed Instant", tone: "armed", hint: "Zero entry delay" },
  armed_max: { label: "Armed Max", tone: "armed", hint: "Zero entry, away" },
  exit_delay: { label: "Exit Delay", tone: "warn", hint: "Leave now" },
  alarm: { label: "ALARM", tone: "alarm", hint: "System in alarm" },
  alarm_in_memory: { label: "Alarm in Memory", tone: "warn", hint: "Recent alarm" },
  not_used: { label: "Offline", tone: "idle", hint: "No data from panel" },
};

export function statusMeta(state: string | undefined): StatusMeta {
  return STATUS[state ?? "not_used"] ?? { label: state ?? "Unknown", tone: "idle", hint: "" };
}

export const ARMED_STATES = new Set([
  "armed_stay",
  "armed_away",
  "armed_instant",
  "armed_max",
]);

export function troubleFlags(led: Record<string, boolean> | undefined): string[] {
  if (!led) return [];
  const flags: string[] = [];
  if (led.low_battery) flags.push("Low Battery");
  if (led.trouble) flags.push("System Trouble");
  if (led.fire) flags.push("Fire");
  if (!led.ac_present) flags.push("AC Power Lost");
  return flags;
}
