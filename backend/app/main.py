"""FastAPI entrypoint. Serves the API under /api and the built React app at /."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.models import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from app.core.config import get_settings

    settings = get_settings()
    if settings.seed_on_start or settings.reseed_on_start:
        from app.seed import seed

        seed(force=settings.reseed_on_start)
    yield


app = FastAPI(title="ObradorIQ", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # single-origin in prod (served together); permissive for dev
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the built frontend if present (Render build step produces frontend/dist).
_FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
)
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
