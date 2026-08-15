from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import db
from ..config import get_settings
from ..security import decrypt_secret, encrypt_secret, hash_password, verify_password
from ..tpi.client import client
from .deps import require_auth

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(require_auth)])


class ConnectionConfig(BaseModel):
    host: Optional[str] = Field(default=None, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    # Envisalink 4 supports up to 10 characters. Write-only.
    password: Optional[str] = Field(default=None, max_length=10)
    # Panel user code (4-6 digits). Stored encrypted, write-only.
    user_code: Optional[str] = Field(default=None, pattern=r"^\d{4,6}$")


@router.get("/connection")
async def get_connection():
    s = get_settings()
    return {
        "host": (await db.get_setting("panel.host")) or s.evl_host,
        "port": int((await db.get_setting("panel.port")) or s.evl_port),
        "password_set": bool((await db.get_setting("panel.password")) or s.evl_password),
        "user_code_set": bool(await db.get_setting("panel.user_code")),
        "connected": client.state.connected,
        "logged_in": client.state.logged_in,
    }


@router.put("/connection")
async def set_connection(cfg: ConnectionConfig):
    if cfg.host is not None:
        await db.set_setting("panel.host", cfg.host)
    if cfg.port is not None:
        await db.set_setting("panel.port", str(cfg.port))
    if cfg.password is not None:
        await db.set_setting("panel.password", encrypt_secret(cfg.password))
    if cfg.user_code is not None:
        await db.set_setting("panel.user_code", encrypt_secret(cfg.user_code))
    client.request_reconnect()
    return await get_connection()


class NotificationPrefs(BaseModel):
    arm_disarm: bool = True
    alarms: bool = True
    troubles: bool = True


@router.get("/notifications")
async def get_notifications():
    prefs = await db.get_setting_json("notify.prefs", NotificationPrefs().model_dump())
    return prefs


@router.put("/notifications")
async def set_notifications(prefs: NotificationPrefs):
    await db.set_setting_json("notify.prefs", prefs.model_dump())
    return prefs


class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=256)


@router.post("/change-password")
async def change_password(body: ChangePassword):
    stored = await db.get_setting("auth.password_hash")
    if not stored or not verify_password(body.current_password, stored):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    await db.set_setting("auth.password_hash", hash_password(body.new_password))
    return {"ok": True}
