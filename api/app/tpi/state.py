from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .protocol import ARMED_STATES


@dataclass
class KeypadState:
    line1: str = ""
    line2: str = ""
    led: dict[str, bool] = field(default_factory=dict)
    beep: str = "off"
    user_or_zone: int = 0


@dataclass
class PanelState:
    """Aggregated live view of the alarm system, derived from TPI messages."""

    connected: bool = False
    logged_in: bool = False
    default_partition: int = 1
    partitions: dict[int, str] = field(default_factory=dict)
    keypads: dict[int, KeypadState] = field(default_factory=dict)
    open_zones: set[int] = field(default_factory=set)
    zone_timers: dict[int, int] = field(default_factory=dict)
    last_update: Optional[str] = None

    def keypad(self, partition: int) -> KeypadState:
        return self.keypads.setdefault(partition, KeypadState())

    def partition_state(self, partition: int = 1) -> str:
        return self.partitions.get(partition, "not_used")

    def is_armed(self, partition: int = 1) -> bool:
        return self.partition_state(partition) in ARMED_STATES

    def flags(self, partition: int = 1) -> dict[str, bool]:
        return self.keypad(partition).led

    def to_dict(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "logged_in": self.logged_in,
            "default_partition": self.default_partition,
            "last_update": self.last_update,
            "partitions": {
                str(p): {
                    "state": state,
                    "armed": state in ARMED_STATES,
                    "keypad": {
                        "line1": self.keypad(p).line1,
                        "line2": self.keypad(p).line2,
                        "led": self.keypad(p).led,
                        "beep": self.keypad(p).beep,
                        "user_or_zone": self.keypad(p).user_or_zone,
                    },
                }
                for p, state in self.partitions.items()
            },
            "open_zones": sorted(self.open_zones),
            "zone_timers": {str(z): t for z, t in sorted(self.zone_timers.items())},
        }
