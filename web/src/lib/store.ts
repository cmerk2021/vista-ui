import { create } from "zustand";
import type { EventRow, PanelState, ZoneRow } from "./types";

interface AppStore {
  panel: PanelState | null;
  wsConnected: boolean;
  liveEvents: EventRow[];
  zones: ZoneRow[];

  setPanel: (panel: PanelState) => void;
  setWsConnected: (connected: boolean) => void;
  addEvent: (event: EventRow) => void;
  setZones: (zones: ZoneRow[]) => void;
}

export const useStore = create<AppStore>((set) => ({
  panel: null,
  wsConnected: false,
  liveEvents: [],
  zones: [],

  setPanel: (panel) => set({ panel }),
  setWsConnected: (wsConnected) => set({ wsConnected }),
  addEvent: (event) =>
    set((s) => ({ liveEvents: [event, ...s.liveEvents].slice(0, 50) })),
  setZones: (zones) => set({ zones }),
}));
