/// <reference lib="webworker" />
import { precacheAndRoute } from "workbox-precaching";

declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: Array<{ url: string; revision: string | null }> };

// Injected by vite-plugin-pwa (injectManifest strategy).
precacheAndRoute(self.__WB_MANIFEST);

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

interface PushPayload {
  title: string;
  body: string;
  tag?: string;
  severity?: "info" | "warning" | "alarm";
  requireInteraction?: boolean;
  vibrate?: number[];
  renotify?: boolean;
  url?: string;
  timestamp?: number;
}

self.addEventListener("push", (event: PushEvent) => {
  let data: PushPayload;
  try {
    data = event.data?.json() as PushPayload;
  } catch {
    data = { title: "Vista", body: event.data?.text() ?? "" };
  }

  const isAlarm = data.severity === "alarm";
  const options: NotificationOptions & {
    vibrate?: number[];
    renotify?: boolean;
    timestamp?: number;
  } = {
    body: data.body,
    tag: data.tag ?? "vista",
    // Alarm notifications stay on screen until dismissed.
    requireInteraction: data.requireInteraction ?? isAlarm,
    renotify: data.renotify ?? true,
    vibrate: data.vibrate ?? (isAlarm ? [400, 120, 400, 120, 400] : [200]),
    icon: "/pwa-192.png",
    badge: "/pwa-192.png",
    timestamp: data.timestamp ?? Date.now(),
    silent: false,
    data: { url: data.url ?? "/", severity: data.severity ?? "info" },
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener("notificationclick", (event: NotificationEvent) => {
  event.notification.close();
  const target = (event.notification.data?.url as string) ?? "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) {
          client.navigate(target).catch(() => undefined);
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
