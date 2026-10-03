"""
BHAM – BACS Help Auto Mapper
Entry point: initialises FastAPI, mounts static files, registers lifecycle hooks.

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8765 --reload
"""

from __future__ import annotations

import os
import sys
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

    from core.hw_discovery import get_host_lan_ips
    lan_ips = get_host_lan_ips()
    logger.info("Listening on http://localhost:%d  –  WS at ws://localhost:%d/api/v1/ws", settings.port, settings.port)
    for ip in lan_ips:
        logger.info("LAN Remote Access: http://%s:%d", ip, settings.port)

    # Avvio eventuale modalità simulatore virtuale (Demo Mode)
    if "--demo" in sys.argv or os.environ.get("BHAM_DEMO", "").lower() in ("1", "true", "yes"):
        from core.simulator import simulator
        await simulator.start()

    # Registro Manovre: recupero transazioni orfane da crash o stacco alimentazione
    from core.audit_journal import audit_journal
    orphans_recovered = audit_journal.recover_orphaned_intents()
    if orphans_recovered:
        logger.warning("⚠️  Registro Manovre: recuperate %d manovre interrotte da stacco alimentazione", orphans_recovered)
    audit_journal.record_event(
        action="system_startup",
        operator="system",
        job_order="SYSTEM",
        details={"version": settings.app_version, "pid": os.getpid()},
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("BHAM shutting down …")
    try:
        audit_journal.record_event(
            action="system_shutdown",
            operator="system",
            job_order="SYSTEM",
            details={"version": settings.app_version},
        )
    except Exception:
        pass
    from core.simulator import simulator
    if simulator.is_active:
        await simulator.stop()
    await manager.shutdown()


API_DESCRIPTION = """
### BACS Help Auto Mapper (BHAM) – Industrial Diagnostics & Mapping Daemon

BHAM è un motore di scansione, discovery as-built e diagnostica di campo per impianti di **Building Automation and Control Systems (BACS)** e **Industrial IoT**.

#### 🔌 Protocolli Supportati:
- **Modbus RTU / RS485**: Scansione attiva multi-baudrate, sweep slave ID (1-247), early exit sentinel IDs, ispezione frame FC43 e smart register scan.
- **Modbus TCP**: Discovery su subnet CIDR e range porte personalizzati con Unit ID sweep.
- **BACnet/IP**: Broadcast Who-Is / I-Am (Annex J), Foreign Device Registration e attraversamento router BBMD con ispezione tabelle BDT/FDT.
- **BACnet MS-TP**: Decodifica passiva token ring e frame Master/Slave su linea seriale RS485.
- **KNXnet/IP**: Discovery multicast UDP 224.0.23.12:3671 con estrazione Individual Addresses e Device Names.
- **Ethernet L2 ARP**: Sniffer passivo promiscuo per censimento host IP silenti e mappatura MAC Vendor OUI.
- **RS485 Bus Health**: Telemetria fisica del bus (Packet Error Rate %, Bus Load %, FPS) con euristica per terminazioni 120Ω mancanti, inversione polarità A(+)/B(-) e rumore.

#### 📖 Documentazione e Strumenti:
- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **Specifica OpenAPI JSON**: `/openapi.json`
- **Live WebSocket Telemetry**: `/api/v1/ws`
"""

TAGS_METADATA = [
    {
        "name": "system",
        "description": "Verifica integrità del demone, stato client WebSocket e diagnostica generale.",
    },
    {
        "name": "setup",
        "description": "Rilevamento periferiche hardware (porte seriali RS485, schede di rete), self-test 1-click e configurazione parametri di campo.",
    },
    {
        "name": "scans",
        "description": "Motori di scansione industriale attivi (Modbus RTU/TCP, BACnet/IP, KNXnet/IP) e sniffer passivi (RS485, ARP).",
    },
    {
        "name": "data",
        "description": "Accesso all'inventario in tempo reale dei dispositivi scoperti (Modbus, BACnet, KNX, Host IP) e mappa topologica gerarchica.",
    },
    {
        "name": "diagnostics",
        "description": "Diagnostica avanzata di campo: telemetria fisica Bus Health RS485, Modbus FC43 Device Identification.",
    },
    {
        "name": "modbus",
        "description": "Ispezione approfondita registri Modbus RTU/TCP e Smart Scan euristico con decodifica automatica dei tipi di dato.",
    },
    {
        "name": "bacnet",
        "description": "Esplorazione dinamica degli oggetti BACnet (Object List) e ispezione router BBMD (tabelle BDT e FDT).",
    },
    {
        "name": "saved-sessions",
        "description": "Gestione snapshot collaudi su disco (salvataggio, ripristino, esportazione JSON) e Session Diff analitico (Prima vs Dopo).",
    },
    {
        "name": "maps",
        "description": "Importazione ed esportazione mappe registri e punti BACS Help compatibili in formato JSON.",
    },
    {
        "name": "reports",
        "description": "Generazione e download dei verbali di as-built in formato Excel multi-foglio (openpyxl) e PDF vettoriale (ReportLab).",
    },
]


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=API_DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
        contact={
            "name": "BACS Help Team",
            "url": "https://www.bacshelp.com",
        },
        license_info={
            "name": "MIT License",
            "url": "https://opensource.org/licenses/MIT",
        },
        lifespan=lifespan,
    )

    # CORS – allow the bundled frontend and local dev servers
    # ⚠️  WARNING: This daemon has NO AUTHENTICATION and listens on 0.0.0.0.
    # Anyone on the network can trigger scans, read discovered devices, export reports.
    # For production/untrusted networks: bind to 127.0.0.1 or add authentication.
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
    from core.paths import get_frontend_dir
    frontend_dir = get_frontend_dir()
    if frontend_dir.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
    else:
        logger.warning("frontend/ directory not found (%s) – UI will not be served.", frontend_dir)

    return app


app = create_app()


# ── Dev entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from bham import open_browser_when_ready

    open_browser_when_ready(f"http://localhost:{settings.port}", port=settings.port)

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
