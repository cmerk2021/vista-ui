from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import close_db, init_db
from .push import ensure_vapid_keys
from .routers import auth, events, panel, push, settings, ws, zones
from .tpi.client import client

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await ensure_vapid_keys()
    await client.start()
    try:
        yield
    finally:
        await client.stop()
        await close_db()


app = FastAPI(title="Vista-UI API", lifespan=lifespan)

_cors = get_settings().cors_origin_list
if _cors:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth.router)
app.include_router(panel.router)
app.include_router(zones.router)
app.include_router(events.router)
app.include_router(push.router)
app.include_router(settings.router)
app.include_router(ws.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "connected": client.state.connected, "logged_in": client.state.logged_in}
