import { useStore } from "./store";
import type { WsMessage } from "./types";

let socket: WebSocket | null = null;
let reconnectTimer: number | undefined;
let shouldRun = false;

function url(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/api/ws`;
}

function handle(message: WsMessage) {
  const store = useStore.getState();
  switch (message.type) {
    case "state":
    case "status":
      store.setPanel(message.state);
      break;
    case "event":
      store.addEvent(message.event);
      break;
    default:
      break;
  }
}

export function connectWs() {
  shouldRun = true;
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  socket = new WebSocket(url());

  socket.onopen = () => useStore.getState().setWsConnected(true);
  socket.onmessage = (ev) => {
    try {
      handle(JSON.parse(ev.data) as WsMessage);
    } catch {
      /* ignore malformed frames */
    }
  };
  socket.onclose = () => {
    useStore.getState().setWsConnected(false);
    socket = null;
    if (shouldRun) {
      window.clearTimeout(reconnectTimer);
      reconnectTimer = window.setTimeout(connectWs, 3000);
    }
  };
  socket.onerror = () => socket?.close();
}

export function disconnectWs() {
  shouldRun = false;
  window.clearTimeout(reconnectTimer);
  socket?.close();
  socket = null;
}
