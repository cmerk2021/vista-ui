import type {
  ConnectionConfig,
  EventRow,
  NotificationPrefs,
  PanelState,
  ZoneRow,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const post = (path: string, body?: unknown) =>
  req(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const put = (path: string, body: unknown) =>
  req(path, { method: "PUT", body: JSON.stringify(body) });

export const api = {
  auth: {
    status: () =>
      req<{ setup_complete: boolean; authenticated: boolean }>("/api/auth/status"),
    setup: (password: string) => post("/api/auth/setup", { password }),
    login: (password: string) => post("/api/auth/login", { password }),
    logout: () => post("/api/auth/logout"),
  },
  panel: {
    status: () => req<PanelState>("/api/panel/status"),
    armAway: (partition = 1) => post("/api/panel/arm-away", { partition }),
    armStay: (partition = 1) => post("/api/panel/arm-stay", { partition }),
    disarm: (partition = 1) => post("/api/panel/disarm", { partition }),
    bypass: (zone: number, partition = 1) => post("/api/panel/bypass", { zone, partition }),
    chime: (partition = 1) => post("/api/panel/chime", { partition }),
    keypress: (key: string, partition = 1) => post("/api/panel/keypress", { key, partition }),
    dumpTimers: () => post("/api/panel/dump-timers"),
  },
  zones: {
    list: () => req<ZoneRow[]>("/api/zones"),
    types: () => req<Record<string, string>>("/api/zones/types"),
    save: (
      number: number,
      body: { name: string | null; zone_type: string | null; icon: string | null },
    ) => put(`/api/zones/${number}`, body),
  },
  events: {
    list: (params: Record<string, string | number | undefined>) => {
      const q = new URLSearchParams();
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== "") q.set(k, String(v));
      }
      return req<{ total: number; limit: number; offset: number; events: EventRow[] }>(
        `/api/events?${q.toString()}`,
      );
    },
  },
  push: {
    publicKey: () => req<{ public_key: string }>("/api/push/public-key"),
    subscribe: (sub: PushSubscriptionJSON) => post("/api/push/subscribe", sub),
    unsubscribe: (endpoint: string) => post("/api/push/unsubscribe", { endpoint }),
    test: () => post("/api/push/test"),
  },
  settings: {
    getConnection: () => req<ConnectionConfig>("/api/settings/connection"),
    setConnection: (body: Partial<{ host: string; port: number; password: string; user_code: string }>) =>
      put("/api/settings/connection", body),
    getNotifications: () => req<NotificationPrefs>("/api/settings/notifications"),
    setNotifications: (body: NotificationPrefs) => put("/api/settings/notifications", body),
    changePassword: (current_password: string, new_password: string) =>
      post("/api/settings/change-password", { current_password, new_password }),
  },
};
