from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from .. import db
from .deps import require_auth

router = APIRouter(prefix="/api/events", tags=["events"], dependencies=[Depends(require_auth)])


@router.get("")
async def list_events(
    zone: Optional[int] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = Query(default=None, pattern=r"^(info|warning|alarm)$"),
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    rows, total = await db.query_events(
        zone=zone, event_type=event_type, severity=severity,
        since=since, until=until, limit=limit, offset=offset,
    )
    return {"total": total, "limit": limit, "offset": offset, "events": rows}
