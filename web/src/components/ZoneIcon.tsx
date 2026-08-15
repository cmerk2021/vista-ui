import {
  DoorOpen,
  AppWindow,
  Radar,
  Waves,
  Flame,
  Cloud,
  Square,
  Shield,
  type LucideIcon,
} from "lucide-react";

const MAP: Record<string, LucideIcon> = {
  door: DoorOpen,
  window: AppWindow,
  motion: Radar,
  glassbreak: Waves,
  smoke: Flame,
  co: Cloud,
  contact: Square,
  generic: Shield,
};

export const ZONE_TYPE_LABELS: Record<string, string> = {
  door: "Door",
  window: "Window",
  motion: "Motion",
  glassbreak: "Glass Break",
  smoke: "Smoke",
  co: "CO",
  contact: "Contact",
  generic: "Generic",
};

export function iconForType(type: string | null | undefined): LucideIcon {
  return MAP[type ?? "generic"] ?? Shield;
}

export function ZoneIcon({ type, size = 20 }: { type: string | null | undefined; size?: number }) {
  const Icon = iconForType(type);
  return <Icon size={size} />;
}
