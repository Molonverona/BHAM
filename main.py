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

# Auto-reexec inside the virtual environment if run directly with system python.
# Mai in modalità congelata (PyInstaller): il binario porta con sé il proprio
# runtime e un eventuale .venv accanto all'eseguibile non va mai eseguito.
if not getattr(sys, "frozen", False) and sys.prefix == getattr(sys, "base_prefix", sys.prefix):
    _venv_py = Path(__file__).resolve().parent / ".venv" / ("bin/python3" if os.name != "nt" else "Scripts/python.exe")
    if _venv_py.exists():
        os.execv(str(_venv_py), [str(_venv_py)] + sys.argv)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
        token_qs = f"?token={settings.api_token}" if settings.lan_auth_required and settings.api_token else ""
        logger.info("LAN Remote Access: http://%s:%d%s", ip, settings.port, token_qs)

    # Apertura automatica del browser all'avvio (se non disabilitata con BHAM_NO_BROWSER=1)
    if not os.environ.get("BHAM_NO_BROWSER"):
        from core.browser import open_browser_when_ready
        open_browser_when_ready(f"http://localhost:{settings.port}", port=settings.port)

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
        from scanners.base import abort_all
        abort_all()
    except Exception:
        pass
    try:
        from scanners.knx import knx_group_monitor
        if knx_group_monitor.is_running:
            await knx_group_monitor.stop()
    except Exception:
        pass
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

    # CORS – compliant configuration (Audit #8 resolved)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # LAN Access Security Middleware (Zero-Config Localhost Exemption & QR Token Pairing)
    @app.middleware("http")
    async def lan_security_middleware(request: Request, call_next):
        client_host = request.client.host if request.client else "127.0.0.1"
        is_local = (
            client_host in ("127.0.0.1", "::1", "localhost", "testclient")
            or client_host.startswith("127.")
        )
        if is_local or not settings.lan_auth_required:
            return await call_next(request)

        path = request.url.path
        # Allow static frontend assets, docs, and public status handshake
        if not path.startswith("/api/v1") and path not in ("/docs", "/redoc", "/openapi.json"):
            return await call_next(request)
        if path in ("/api/v1/health", "/api/v1/network/qr-code", "/api/v1/network/qr"):
            return await call_next(request)

        # Check authentication token
        token = request.headers.get("X-BHAM-Token") or request.query_params.get("token")
        if token and settings.verify_token(token):
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={
                "detail": "Autenticazione richiesta per accesso remoto da rete LAN.",
                "hint": "Fornire header 'X-BHAM-Token' o scansionare il QR code di accoppiamento mobile.",
            },
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


# ── Entry-point (sorgente, venv e binario congelato PyInstaller) ──────────────

def server_target() -> "FastAPI | str":
    """
    Restituisce il target ASGI da consegnare a uvicorn.

    In modalità congelata (PyInstaller) lo script di ingresso viene eseguito come
    ``__main__`` e il modulo ``main`` NON è importabile: passare la stringa
    ``"main:app"`` farebbe terminare immediatamente l'eseguibile con
    ``Error loading ASGI app. Could not import module "main"``.
    Si consegna quindi direttamente l'oggetto applicazione.

    Da sorgente si mantiene invece la stringa di import, indispensabile per
    l'auto-reload in sviluppo.
    """
    from core.paths import is_frozen
    return app if is_frozen() else "main:app"


def build_arg_parser() -> "argparse.ArgumentParser":
    import argparse

    parser = argparse.ArgumentParser(
        prog="bham",
        description="BHAM – BACS Help Auto Mapper (demone di discovery e diagnostica BACS).",
    )
    parser.add_argument("--host", default=settings.host,
                        help=f"indirizzo di ascolto (default: {settings.host})")
    parser.add_argument("--port", type=int, default=settings.port,
                        help=f"porta di ascolto (default: {settings.port})")
    parser.add_argument("--no-browser", action="store_true",
                        help="non aprire automaticamente il browser")
    parser.add_argument("--demo", action="store_true",
                        help="avvia con il simulatore di impianto virtuale (Demo Mode)")
    parser.add_argument("--no-port-fallback", action="store_true",
                        help="non cercare una porta alternativa se quella richiesta è occupata")
    parser.add_argument("--check", action="store_true",
                        help="esegue solo le verifiche di preflight ed esce (0 = OK, 1 = problemi)")
    parser.add_argument("--version", action="version",
                        version=f"BHAM {settings.app_version}")
    return parser


def _print_preflight(report) -> None:
    """Stampa in console l'esito delle verifiche di preflight."""
    for warning in report.warnings:
        print(f"[!] {warning}")
    for error in report.errors:
        print(f"[ERRORE] {error}")


def run_cli(argv: list[str] | None = None) -> int:
    """Punto di ingresso a riga di comando, condiviso da sorgente e binario congelato."""
    import uvicorn

    from core.browser import open_browser_when_ready
    from core.preflight import run_preflight

    args = build_arg_parser().parse_args(argv)

    if args.demo:
        os.environ["BHAM_DEMO"] = "1"

    report = run_preflight(
        port=args.port,
        host=args.host,
        allow_port_fallback=not args.no_port_fallback,
    )
    _print_preflight(report)

    if args.check:
        if report.is_healthy:
            print(f"[OK] Preflight superato – porta di ascolto {report.resolved_port}.")
            return 0
        return 1

    if not report.is_healthy:
        print("\nAvvio annullato: risolvi i problemi elencati sopra e riprova.")
        return 1

    # Allinea la configurazione globale alla porta realmente utilizzata, così che
    # log di avvio, QR code di pairing e URL LAN riportino il valore corretto.
    settings.host = args.host
    settings.port = report.resolved_port

    if not args.no_browser:
        open_browser_when_ready(f"http://localhost:{settings.port}", port=settings.port)
    # In ogni caso il lifespan non deve riaprire il browser: qui sopra è già
    # stato pianificato sulla porta risolta, oppure l'utente l'ha disabilitato.
    os.environ["BHAM_NO_BROWSER"] = "1"

    target = server_target()
    try:
        uvicorn.run(
            target,
            host=settings.host,
            port=settings.port,
            # L'auto-reload richiede una stringa di import: non è disponibile
            # (né desiderabile) quando si passa l'oggetto applicazione.
            reload=settings.debug and isinstance(target, str),
            log_level="debug" if settings.debug else "info",
        )
    except KeyboardInterrupt:
        print("\nArresto di BHAM.")
    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
