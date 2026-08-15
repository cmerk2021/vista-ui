from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .. import db
from ..bus import bus
from ..tpi.client import client
from .deps import require_auth

router = APIRouter(prefix="/api/zones", tags=["zones"], dependencies=[Depends(require_auth)])

# Curated zone types -> Lucide icon names used by the frontend.
ZONE_TYPES = {
    "door": "door-open",
    "window": "app-window",
    "motion": "radar",
    "glassbreak": "unfold-horizontal",
    "smoke": "flame",
    "co": "cloud",
    "contact": "square",
    "generic": "shield",
}


class ZoneConfig(BaseModel):
    name: Optional[str] = Field(default=None, max_length=64)
    zone_type: Optional[str] = Field(default=None)
    icon: Optional[str] = Field(default=None, max_length=64)


@router.get("/types")
async def zone_types():
    return ZONE_TYPES


@router.get("")
async def list_zones():
    configs = {z["number"]: z for z in await db.list_zones()}
    open_zones = client.state.open_zones
    timers = client.state.zone_timers
    result = []
    for number in sorted(set(configs) | open_zones | set(timers)):
        cfg = configs.get(number, {})
        result.append(
            {
                "number": number,
                "name": cfg.get("name"),
                "zone_type": cfg.get("zone_type"),
                "icon": cfg.get("icon"),
                "configured": bool(cfg.get("name")),
                "open": number in open_zones,
                "seconds_since_seen": timers.get(number),
            }
        )
    return result


@router.put("/{number}")
async def set_zone(number: int, body: ZoneConfig):
    icon = body.icon or (ZONE_TYPES.get(body.zone_type or "", None))
    zone = await db.set_zone_config(number, body.name, body.zone_type, icon)
    bus.publish({"type": "zone_config", "zone": zone})
    return zone
