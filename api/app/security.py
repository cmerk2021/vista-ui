from __future__ import annotations

import base64
import hashlib
import time
from typing import Optional

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from .config import get_settings

_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days
_ALGO = "HS256"


def _secret() -> str:
    return get_settings().app_secret


# --- password hashing -------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- session tokens (signed JWT, delivered as httpOnly cookie) --------------

def create_session_token() -> str:
    now = int(time.time())
    payload = {"sub": "owner", "iat": now, "exp": now + _SESSION_TTL_SECONDS}
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def verify_session_token(token: str) -> bool:
    try:
        jwt.decode(token, _secret(), algorithms=[_ALGO])
        return True
    except jwt.PyJWTError:
        return False


# --- at-rest encryption for the panel user code / EVL password --------------

def _fernet() -> Fernet:
    # Derive a stable 32-byte key from APP_SECRET.
    digest = hashlib.sha256(_secret().encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return None
