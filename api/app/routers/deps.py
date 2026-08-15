from __future__ import annotations

from fastapi import Cookie, HTTPException, status

from ..db import get_setting
from ..security import verify_session_token

SESSION_COOKIE = "vista_session"


async def is_setup_complete() -> bool:
    return (await get_setting("auth.password_hash")) is not None


async def require_auth(vista_session: str | None = Cookie(default=None)) -> None:
    if not vista_session or not verify_session_token(vista_session):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
