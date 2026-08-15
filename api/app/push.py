"""Web Push (VAPID) notifications via pywebpush. No third-party service.

Honest platform note: standard Web Push on iOS Safari/PWAs cannot bypass Do Not
Disturb / Focus. Apple's critical-alert entitlement is native-app only. For
alarm-level events we use every attention-grabbing option the Web Push /
Notifications API actually allows (requireInteraction, urgent vibration/sound
hints, retriggering) but we do NOT and cannot guarantee DND bypass.
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException, webpush

from . import db

_VAPID_SUBJECT = "mailto:admin@vista.local"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


async def ensure_vapid_keys() -> str:
    """Generate and persist VAPID keys on first run. Returns the public key."""
    pub = await db.get_setting("vapid.public")
    priv = await db.get_setting("vapid.private")
    if pub and priv:
        return pub

    key = ec.generate_private_key(ec.SECP256R1())
    priv_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    raw_pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    pub_b64 = _b64url(raw_pub)
    await db.set_setting("vapid.private", priv_pem)
    await db.set_setting("vapid.public", pub_b64)
    return pub_b64


async def get_public_key() -> Optional[str]:
    return await db.get_setting("vapid.public")


class Notifier:
    """Sends Web Push messages to all stored subscriptions, with per-tag cooldown."""

    def __init__(self) -> None:
        self._last_sent: dict[str, float] = {}

    async def _send_one(self, sub: dict, payload: dict[str, Any], urgency: str) -> None:
        priv = await db.get_setting("vapid.private")
        if not priv:
            return
        sub_info = {
            "endpoint": sub["endpoint"],
            "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
        }
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info=sub_info,
                data=json.dumps(payload),
                vapid_private_key=priv,
                vapid_claims={"sub": _VAPID_SUBJECT},
                headers={"Urgency": urgency},
                ttl=600,
            )
        except WebPushException as exc:
            # 404/410 => subscription gone; prune it.
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                await db.remove_push_subscription(sub["endpoint"])

    async def send(self, payload: dict[str, Any], urgency: str = "normal") -> None:
        subs = await db.list_push_subscriptions()
        await asyncio.gather(*(self._send_one(s, payload, urgency) for s in subs))

    async def notify(
        self,
        *,
        tag: str,
        title: str,
        body: str,
        severity: str = "info",
        require_interaction: bool = False,
        cooldown: float = 0.0,
        url: str = "/",
    ) -> None:
        """Send a push respecting a per-tag cooldown (for retrigger throttling)."""
        now = time.time()
        if cooldown and (now - self._last_sent.get(tag, 0.0)) < cooldown:
            return
        self._last_sent[tag] = now

        vibrate = [400, 120, 400, 120, 400] if severity == "alarm" else [200]
        payload = {
            "title": title,
            "body": body,
            "tag": tag,
            "severity": severity,
            "requireInteraction": require_interaction or severity == "alarm",
            "vibrate": vibrate,
            "renotify": True,
            "url": url,
            "timestamp": int(now * 1000),
        }
        urgency = "high" if severity in ("alarm", "warning") else "normal"
        await self.send(payload, urgency=urgency)


notifier = Notifier()
