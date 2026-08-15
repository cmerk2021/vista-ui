from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from .. import db
from ..push import ensure_vapid_keys, get_public_key, notifier
from .deps import require_auth

router = APIRouter(prefix="/api/push", tags=["push"], dependencies=[Depends(require_auth)])


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class Subscription(BaseModel):
    endpoint: str
    keys: SubscriptionKeys


@router.get("/public-key")
async def public_key():
    key = await get_public_key()
    if not key:
        key = await ensure_vapid_keys()
    return {"public_key": key}


@router.post("/subscribe")
async def subscribe(sub: Subscription, request: Request):
    await db.add_push_subscription(
        endpoint=sub.endpoint,
        p256dh=sub.keys.p256dh,
        auth=sub.keys.auth,
        ua=request.headers.get("user-agent"),
    )
    return {"ok": True}


class Unsubscribe(BaseModel):
    endpoint: str


@router.post("/unsubscribe")
async def unsubscribe(body: Unsubscribe):
    await db.remove_push_subscription(body.endpoint)
    return {"ok": True}


@router.post("/test")
async def test_push():
    await notifier.notify(
        tag="test", title="Vista test notification",
        body="Web Push is working.", severity="info",
    )
    return {"ok": True}
