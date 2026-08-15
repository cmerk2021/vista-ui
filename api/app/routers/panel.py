from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..tpi.client import client
from .deps import require_auth

router = APIRouter(prefix="/api/panel", tags=["panel"], dependencies=[Depends(require_auth)])


@router.get("/status")
async def status():
    return client.state.to_dict()


class PartitionBody(BaseModel):
    partition: int = Field(default=1, ge=1, le=8)


class BypassBody(PartitionBody):
    zone: int = Field(ge=1, le=128)


class KeypressBody(PartitionBody):
    key: str = Field(min_length=1, max_length=1, pattern=r"^[0-9A-D#*]$")


def _guard_connected() -> None:
    if not client.state.logged_in:
        raise HTTPException(status_code=503, detail="Not connected to Envisalink")


@router.post("/arm-away")
async def arm_away(body: PartitionBody):
    _guard_connected()
    try:
        await client.arm_away(body.partition)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/arm-stay")
async def arm_stay(body: PartitionBody):
    _guard_connected()
    try:
        await client.arm_stay(body.partition)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/disarm")
async def disarm(body: PartitionBody):
    _guard_connected()
    try:
        await client.disarm(body.partition)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/bypass")
async def bypass(body: BypassBody):
    _guard_connected()
    try:
        await client.bypass_zone(body.zone, body.partition)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/chime")
async def chime(body: PartitionBody):
    _guard_connected()
    try:
        await client.toggle_chime(body.partition)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@router.post("/keypress")
async def keypress(body: KeypressBody):
    _guard_connected()
    await client.send_keys(body.key, body.partition)
    return {"ok": True}


@router.post("/dump-timers")
async def dump_timers():
    _guard_connected()
    await client.dump_zone_timers()
    return {"ok": True}
