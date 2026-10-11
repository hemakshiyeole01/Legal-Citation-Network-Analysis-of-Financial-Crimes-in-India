"""Application factory (importable without loading any data until called)."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config.settings import Settings
from src.api.routers import cases, domains, search, tables
from src.utils.data_store import DataStore

STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description="Citation network of Indian Supreme Court judgments in five crime domains.",
    )
    app.state.settings = settings
    app.state.store = DataStore(settings)

    app.include_router(domains.router)
    app.include_router(search.router)
    app.include_router(cases.router)
    app.include_router(tables.router)

    @app.get("/health", tags=["meta"], summary="Is the API up, and what data did it load?")
    def health():
        return {"status": "ok", **app.state.store.overview()}

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    return app

