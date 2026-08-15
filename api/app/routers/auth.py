from __future__ import annotations

from fastapi import APIRouter, Cookie, HTTPException, Response, status
from pydantic import BaseModel, Field

from ..db import get_setting, set_setting
from ..security import create_session_token, hash_password, verify_password, verify_session_token
from .deps import SESSION_COOKIE, is_setup_complete

router = APIRouter(prefix="/api/auth", tags=["auth"])

# 30 days, matching the session token TTL.
_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


class PasswordBody(BaseModel):
    password: str = Field(min_length=8, max_length=256)


def _set_session_cookie(response: Response) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(),
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


@router.get("/status")
async def auth_status(vista_session: str | None = Cookie(default=None)):
    authenticated = bool(vista_session and verify_session_token(vista_session))
    return {"setup_complete": await is_setup_complete(), "authenticated": authenticated}


@router.post("/setup")
async def setup(body: PasswordBody, response: Response):
    if await is_setup_complete():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Setup already completed")
    await set_setting("auth.password_hash", hash_password(body.password))
    _set_session_cookie(response)
    return {"ok": True}


@router.post("/login")
async def login(body: PasswordBody, response: Response):
    stored = await get_setting("auth.password_hash")
    if not stored or not verify_password(body.password, stored):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
    _set_session_cookie(response)
    return {"ok": True}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}
