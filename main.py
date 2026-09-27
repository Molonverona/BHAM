"""
BHAM – BACS Help Auto Mapper
Entry point: initialises FastAPI, mounts static files, registers lifecycle hooks.

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8765 --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import router
from api.websockets import manager
from core.config import settings
from core.logger import logger
from core.priv_check import check_privileges
from data.state import state


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info("╔══════════════════════════════════════╗")
    logger.info("║  BHAM v%s – starting up …       ║", settings.app_version)
    logger.info("╚══════════════════════════════════════╝")

    # Check OS-level privileges (logs warnings – never raises)
    check_privileges()

    # Wire WebSocket broadcast into the state singleton
    state.register_broadcast_hook(manager.enqueue_state_event)

    # Start the WS pump task
    await manager.startup()

    logger.info(
        "Listening on http://%s:%d  –  WS at ws://%s:%d/ws",
        settings.host, settings.port,
        settings.host, settings.port,
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("BHAM shutting down …")
    await manager.shutdown()


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Network discovery and diagnostics daemon for building automation "
            "and industrial IoT (Modbus RTU/TCP, BACnet IP/MS-TP)."
        ),
        lifespan=lifespan,
    )

    # CORS – allow the bundled frontend and local dev servers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST + WS routes
    app.include_router(router, prefix="/api/v1")

    # Serve frontend static files
    frontend_dir = Path(__file__).parent / "frontend"
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    else:
        logger.warning("frontend/ directory not found – UI will not be served.")

    return app


app = create_app()


# ── Dev entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
