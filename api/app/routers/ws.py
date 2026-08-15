from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..bus import bus
from ..security import verify_session_token
from ..tpi.client import client
from .deps import SESSION_COOKIE

router = APIRouter()


@router.websocket("/api/ws")
async def ws(websocket: WebSocket) -> None:
    token = websocket.cookies.get(SESSION_COOKIE)
    if not token or not verify_session_token(token):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    queue = bus.subscribe()
    # Prime the client with the current full state.
    await websocket.send_json({"type": "state", "state": client.state.to_dict()})
    try:
        while True:
            message = await queue.get()
            await websocket.send_json(message)
    except (WebSocketDisconnect, asyncio.CancelledError, RuntimeError):
        pass
    finally:
        bus.unsubscribe(queue)
