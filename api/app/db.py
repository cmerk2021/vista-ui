from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from .config import get_settings

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")

_db: Optional[aiosqlite.Connection] = None


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> None:
    global _db
    settings = get_settings()
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(settings.db_path)
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL;")
    await _db.execute("PRAGMA foreign_keys=ON;")
    await _db.executescript(_SCHEMA)
    await _db.commit()


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


def db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


# --- settings key/value -----------------------------------------------------

async def get_setting(key: str) -> Optional[str]:
    async with db().execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
        row = await cur.fetchone()
    return row["value"] if row else None


async def set_setting(key: str, value: Optional[str]) -> None:
    await db().execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    await db().commit()


async def get_setting_json(key: str, default: Any = None) -> Any:
    raw = await get_setting(key)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


async def set_setting_json(key: str, value: Any) -> None:
    await set_setting(key, json.dumps(value))


# --- events -----------------------------------------------------------------

async def insert_event(
    *,
    event_type: str,
    severity: str = "info",
    partition: Optional[int] = None,
    zone: Optional[int] = None,
    user_num: Optional[int] = None,
    status: Optional[str] = None,
    detail: Optional[str] = None,
    raw: Optional[str] = None,
) -> dict:
    ts = utcnow_iso()
    cur = await db().execute(
        "INSERT INTO events(ts, event_type, partition, zone, user_num, status, severity, detail, raw) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ts, event_type, partition, zone, user_num, status, severity, detail, raw),
    )
    await db().commit()
    return {
        "id": cur.lastrowid,
        "ts": ts,
        "event_type": event_type,
        "partition": partition,
        "zone": zone,
        "user_num": user_num,
        "status": status,
        "severity": severity,
        "detail": detail,
        "raw": raw,
    }


async def query_events(
    *,
    zone: Optional[int] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    where: list[str] = []
    params: list[Any] = []
    if zone is not None:
        where.append("zone = ?")
        params.append(zone)
    if event_type:
        where.append("event_type = ?")
        params.append(event_type)
    if severity:
        where.append("severity = ?")
        params.append(severity)
    if since:
        where.append("ts >= ?")
        params.append(since)
    if until:
        where.append("ts <= ?")
        params.append(until)
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    async with db().execute(f"SELECT COUNT(*) AS n FROM events{clause}", params) as cur:
        total = (await cur.fetchone())["n"]

    async with db().execute(
        f"SELECT * FROM events{clause} ORDER BY id DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]
    return rows, total


# --- zones ------------------------------------------------------------------

async def upsert_zone_seen(number: int) -> None:
    """Register a zone number the first time it appears so it shows as unconfigured."""
    now = utcnow_iso()
    await db().execute(
        "INSERT INTO zones(number, created_at, updated_at) VALUES(?, ?, ?) "
        "ON CONFLICT(number) DO NOTHING",
        (number, now, now),
    )
    await db().commit()


async def set_zone_config(number: int, name: Optional[str], zone_type: Optional[str], icon: Optional[str]) -> dict:
    now = utcnow_iso()
    await db().execute(
        "INSERT INTO zones(number, name, zone_type, icon, created_at, updated_at) "
        "VALUES(?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(number) DO UPDATE SET name=excluded.name, zone_type=excluded.zone_type, "
        "icon=excluded.icon, updated_at=excluded.updated_at",
        (number, name, zone_type, icon, now, now),
    )
    await db().commit()
    return await get_zone(number)  # type: ignore[return-value]


async def get_zone(number: int) -> Optional[dict]:
    async with db().execute("SELECT * FROM zones WHERE number = ?", (number,)) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def list_zones() -> list[dict]:
    async with db().execute("SELECT * FROM zones ORDER BY number") as cur:
        return [dict(r) for r in await cur.fetchall()]


# --- push subscriptions -----------------------------------------------------

async def add_push_subscription(endpoint: str, p256dh: str, auth: str, ua: Optional[str]) -> None:
    await db().execute(
        "INSERT INTO push_subscriptions(endpoint, p256dh, auth, ua, created_at) "
        "VALUES(?, ?, ?, ?, ?) "
        "ON CONFLICT(endpoint) DO UPDATE SET p256dh=excluded.p256dh, auth=excluded.auth",
        (endpoint, p256dh, auth, ua, utcnow_iso()),
    )
    await db().commit()


async def remove_push_subscription(endpoint: str) -> None:
    await db().execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
    await db().commit()


async def list_push_subscriptions() -> list[dict]:
    async with db().execute("SELECT * FROM push_subscriptions") as cur:
        return [dict(r) for r in await cur.fetchall()]
