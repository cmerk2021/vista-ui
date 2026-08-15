export interface KeypadState {
  line1: string;
  line2: string;
  led: Record<string, boolean>;
  beep: string;
  user_or_zone: number;
}

export interface PartitionState {
  state: string;
  armed: boolean;
  keypad: KeypadState;
}

export interface PanelState {
  connected: boolean;
  logged_in: boolean;
  default_partition: number;
  last_update: string | null;
  partitions: Record<string, PartitionState>;
  open_zones: number[];
  zone_timers: Record<string, number>;
}

export interface EventRow {
  id: number;
  ts: string;
  event_type: string;
  partition: number | null;
  zone: number | null;
  user_num: number | null;
  status: string | null;
  severity: "info" | "warning" | "alarm";
  detail: string | null;
  raw: string | null;
}

export interface ZoneRow {
  number: number;
  name: string | null;
  zone_type: string | null;
  icon: string | null;
  configured: boolean;
  open: boolean;
  seconds_since_seen: number | null;
}

export interface ConnectionConfig {
  host: string;
  port: number;
  password_set: boolean;
  user_code_set: boolean;
  connected: boolean;
  logged_in: boolean;
}

export interface NotificationPrefs {
  arm_disarm: boolean;
  alarms: boolean;
  troubles: boolean;
}

export type WsMessage =
  | { type: "state" | "status"; state: PanelState }
  | { type: "event"; event: EventRow }
  | { type: "ack"; command: string; code: string; message: string }
  | { type: "zone_config"; zone: ZoneRow };
