from __future__ import annotations

import asyncio
from typing import Any


class EventBus:
    """Minimal fan-out pub/sub for pushing live updates to WebSocket clients."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(q)

    def publish(self, message: dict[str, Any]) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                # Drop the slowest consumer's oldest item to stay live.
                try:
                    q.get_nowait()
                    q.put_nowait(message)
                except asyncio.QueueEmpty:
                    pass


bus = EventBus()
