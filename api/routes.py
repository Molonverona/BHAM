"""
BHAM – REST API Routes
All HTTP endpoints and WebSocket connection handler.
Full OpenAPI/Swagger integration with typed request and response schemas.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from api.schemas import (
    ARPSniffRequest,
    BACnetIPScanRequest,
    BACnetObjectExplorerResponse,
    BACnetPointOverrideRequest,
    BACnetPointOverrideResponse,
    BACnetRelinquishRequest,
    ConfigActiveResponse,
    ConfigureRequest,
    ConfigureResponse,
    DeleteSessionResponse,
    DemoStatusResponse,
    DemoToggleResponse,
    FC43Request,
    FC43Response,
    HardwareSelfTestResponse,
    HealthResponse,
    IPScanRequest,
    KNXIPScanRequest,
    MapsImportResponse,
    ModbusQuickReadRequest,
    ModbusQuickReadResponse,
    ModbusQuickWriteRequest,
    ModbusQuickWriteResponse,
    ModbusRTUScanRequest,
    ModbusSmartScanBody,
    ModbusSmartScanResponse,
    ModbusTCPScanRequest,
    NetworkInterfacesResponse,
    OUILookupResponse,
    RestoreSessionResponse,
    SaveCustomProfileRequest,
    SaveSessionRequest,
    SaveSessionResponse,
    SafeModeArmRequest,
    SafeModeStatusResponse,
    ScanAbortResponse,
    ScanAbortSingleResponse,
    ScanActionResponse,
    SerialPortInfo,
    SerialSniffRequest,
    SlaveMapResponse,
    StateClearResponse,
    AuditExportResponse,
    AuditIntegrityResponse,
    AuditJournalEntry,
    ApplyProfileRequest,
    ApplyProfileResponse,
    ProfileDetail,
    ProfileMeta,
)
from api.websockets import manager
from core.config import settings
from core.logger import logger
from data.models import (
    BACnetDevice,
    BBDTEntry,
    BBMDInfoResponse,
    BusHealth,
    FDTEntry,
    IPHost,
    KNXDevice,
    ModbusDevice,
    Protocol,
    SavedSessionMeta,
    ScanSession,
    SessionConfig,
    SessionDiffRequest,
    SessionDiffResult,
)
from data.state import state

router = APIRouter()


# ── Health & System ───────────────────────────────────────────────────────────

@router.get(
    "/health",
    tags=["system"],
    response_model=HealthResponse,
    summary="Verifica stato e heartbeat del servizio",
    description="Ritorna lo stato del demone BHAM, il numero di client WebSocket attivi e la versione corrente.",
)
async def health() -> dict:
    return {
        "status": "ok",
        "active_ws": manager.active_connections_count(),
        "version": settings.app_version,
    }


# ── State snapshot ────────────────────────────────────────────────────────────

@router.get(
    "/state",
    tags=["data"],
    summary="Snapshot completo dell'inventario dispositivi",
    description="Ritorna lo snapshot in tempo reale di tutti i dispositivi catalogati (Modbus, BACnet, KNX, Host IP), canali e sessioni attive.",
)
async def get_state() -> dict:
    return state.snapshot()


@router.get(
    "/topology",
    tags=["data"],
    summary="Mappa topologica gerarchica dell'impianto",
    description="Genera il grafo topologico orientato dell'impianto BMS con nodi radice, canali fisici (RS485/Ethernet), router BBMD e dispositivi di campo.",
)
async def get_topology() -> dict:
    return state.get_topology()


@router.delete(
    "/state",
    tags=["data"],
    response_model=StateClearResponse,
    summary="Azzera la memoria attiva dei dispositivi",
    description="Rimuove tutti i dispositivi scoperti e resetta i contatori di collaudo. Non modifica le sessioni archiviate su disco.",
)
async def clear_state() -> dict:
    state.clear()
    return {"cleared": True}


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.get(
    "/sessions",
    tags=["scans"],
    response_model=list[ScanSession],
    summary="Elenco sessioni di scansione attive o recenti",
    description="Ritorna l'elenco delle sessioni di scansione create in memoria durante il ciclo di vita corrente del demone.",
)
async def list_sessions() -> list[dict]:
    return [s.model_dump(mode="json") for s in state.sessions.values()]


@router.get(
    "/sessions/{session_id}",
    tags=["scans"],
    response_model=ScanSession,
    summary="Dettaglio di una specifica sessione di scansione",
    description="Recupera i dettagli, lo stato e i parametri di avvio della sessione specificata tramite UUID.",
)
async def get_session(session_id: str) -> dict:
    session = state.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump(mode="json")


# ── Scan trigger endpoints ────────────────────────────────────────────────────

@router.post(
    "/scan/modbus/rtu",
    tags=["scans"],
    response_model=ScanActionResponse,
    summary="Avvia scansione attiva Modbus RTU (RS485)",
    description="Avvia un task in background che prova la matrice di baudrate e parità sui nodi indicati (1-247) con euristica Early Exit.",
)
async def start_modbus_rtu(req: ModbusRTUScanRequest) -> dict:
    from scanners.modbus import ModbusScanner
    session = state.new_session(Protocol.MODBUS_RTU, req.model_dump())
    scanner = ModbusScanner(session_id=session.id)
    scanner.reset_abort()
    asyncio.create_task(scanner.scan_rtu(req))
    return {"session_id": session.id, "status": "started"}


@router.post(
    "/scan/serial/sniff",
    tags=["scans"],
    response_model=ScanActionResponse,
    summary="Avvia sniffer passivo bus seriale RS485 (Zero-TX)",
    description="Ascolta in modalità promiscua senza trasmettere bit sul bus. Decodifica frame Modbus RTU e BACnet MS-TP e calcola la salute fisica del bus.",
)
async def start_serial_sniff(req: SerialSniffRequest) -> dict:
    from scanners.serial_sniffer import SerialSniffer
    proto = Protocol.MODBUS_RTU if req.protocol_filter == "modbus_rtu" else (
        Protocol.BACNET_MSTP if req.protocol_filter == "bacnet_mstp" else Protocol.UNKNOWN
    )
    session = state.new_session(proto, req.model_dump())
    sniffer = SerialSniffer(session_id=session.id)
    sniffer.reset_abort()
    asyncio.create_task(sniffer.sniff(req))
    return {"session_id": session.id, "status": "started"}


@router.post(
    "/scan/modbus/tcp",
    tags=["scans"],
    response_model=ScanActionResponse,
    summary="Avvia scansione attiva Modbus TCP su host o subnet CIDR",
    description="Sonda gli indirizzi IP e porte specificate (default 502) per rilevare gateway e slave Modbus TCP.",
)
async def start_modbus_tcp(req: ModbusTCPScanRequest) -> dict:
    from scanners.modbus import ModbusScanner
    session = state.new_session(Protocol.MODBUS_TCP, req.model_dump())
    scanner = ModbusScanner(session_id=session.id)
    scanner.reset_abort()
    asyncio.create_task(scanner.scan_tcp(req))
    return {"session_id": session.id, "status": "started"}


@router.post(
    "/scan/bacnet/ip",
    tags=["scans"],
    response_model=ScanActionResponse,
    summary="Avvia scansione Who-Is broadcast BACnet/IP",
    description="Invia sonde broadcast Who-Is sulle porte specificate (es. BAC0 47808) e opzionalmente si registra come Foreign Device su un router BBMD.",
)
async def start_bacnet_ip(req: BACnetIPScanRequest) -> dict:
    from scanners.bacnet import BACnetScanner
    session = state.new_session(Protocol.BACNET_IP, req.model_dump())
    scanner = BACnetScanner(session_id=session.id)
    scanner.reset_abort()
    asyncio.create_task(scanner.scan_ip(req))
    return {"session_id": session.id, "status": "started"}


@router.post(
    "/scan/knx/ip",
    tags=["scans"],
    response_model=ScanActionResponse,
    summary="Avvia discovery multicast KNXnet/IP",
    description="Invia messaggi di Search Request sul gruppo multicast 224.0.23.12:3671 e catalogata interfacce e router KNX.",
)
async def start_knx_ip(req: KNXIPScanRequest) -> dict:
    from scanners.knx import KNXScanner
    session = state.new_session(Protocol.KNX_IP, req.model_dump())
    scanner = KNXScanner(session_id=session.id)
    scanner.reset_abort()
    asyncio.create_task(scanner.scan(req))
    return {"session_id": session.id, "status": "started"}


@router.post(
    "/scan/arp",
    tags=["scans"],
    response_model=ScanActionResponse,
    summary="Avvia sniffer passivo promiscuo ARP L2",
    description="Cattura pacchetti ARP broadcast per identificare tutti gli host IP attivi nella LAN anche se non rispondono a ICMP ping.",
)
async def start_arp_sniff(req: ARPSniffRequest) -> dict:
    from scanners.ip_sniffer import IPSniffer
    session = state.new_session(Protocol.UNKNOWN, req.model_dump())
    sniffer = IPSniffer(session_id=session.id)
    sniffer.reset_abort()
    asyncio.create_task(sniffer.sniff(req))
    return {"session_id": session.id, "status": "started"}


@router.post(
    "/scan/ip",
    tags=["scans"],
    response_model=ScanActionResponse,
    summary="Avvia scansione attiva subnet BACS IP",
    description="Sonda la subnet o range CIDR specificato per identificare tutti gli host IP attivi, estrarre il MAC address, determinare il Vendor OUI (Schneider, Siemens, Honeywell, ecc.), risolvere hostname e testare porte e servizi BACS/IoT (502, 47808, 3671, 80, 443, 8080, 8443, 1911, 1883).",
)
async def start_ip_scan(req: IPScanRequest) -> dict:
    from scanners.ip_scanner import IPScanner
    session = state.new_session(Protocol.UNKNOWN, req.model_dump())
    scanner = IPScanner(session_id=session.id)
    scanner.reset_abort()
    asyncio.create_task(scanner.scan(req))
    return {"session_id": session.id, "status": "started"}


@router.post(
    "/scan/abort",
    tags=["scans"],
    response_model=ScanAbortResponse,
    summary="Arresto d'emergenza globale (Abort all)",
    description="Invia il segnale di abort immediato a tutti i motori di scansione e sniffer in esecuzione, rilasciando subito porte seriali e socket.",
)
async def abort_all_scans() -> dict:
    from scanners.base import abort_all
    return {"aborted": True, "sessions": abort_all()}


@router.post(
    "/scan/abort/{session_id}",
    tags=["scans"],
    response_model=ScanAbortSingleResponse,
    summary="Arresta una singola sessione di scansione",
    description="Invia il segnale di stop alla sessione specificata tramite UUID.",
)
async def abort_scan(session_id: str) -> dict:
    from scanners.base import abort_session
    abort_session(session_id)
    return {"aborted": True}


# ── Devices ───────────────────────────────────────────────────────────────────

@router.get(
    "/devices/modbus",
    tags=["data"],
    response_model=list[ModbusDevice],
    summary="Elenco dispositivi Modbus RTU/TCP rilevati",
    description="Restituisce l'inventario completo degli slave Modbus scoperti con parametri seriali o IP, latenza ms e registri.",
)
async def get_modbus_devices() -> list[dict]:
    return [d.model_dump(mode="json") for d in state.modbus_devices.values()]


@router.get(
    "/devices/bacnet",
    tags=["data"],
    response_model=list[BACnetDevice],
    summary="Elenco dispositivi BACnet/IP e MS-TP rilevati",
    description="Restituisce l'inventario dei dispositivi BACnet con Device ID, vendor name, model, firmware revision e conteggio oggetti.",
)
async def get_bacnet_devices() -> list[dict]:
    return [d.model_dump(mode="json") for d in state.bacnet_devices.values()]


@router.get(
    "/devices/knx",
    tags=["data"],
    response_model=list[KNXDevice],
    summary="Elenco dispositivi KNXnet/IP rilevati",
    description="Restituisce i router e interfacce KNXnet/IP con Individual Address (Area.Linea.Dispositivo) e nome dispositivo.",
)
async def get_knx_devices() -> list[dict]:
    return [k.model_dump(mode="json") for k in state.knx_devices.values()]


@router.get(
    "/devices/hosts",
    tags=["data"],
    response_model=list[IPHost],
    summary="Elenco host IP rilevati passivamente",
    description="Restituisce gli endpoint Ethernet scoperti tramite sniffing ARP con IP, MAC address e identificativo Vendor OUI.",
)
async def get_ip_hosts() -> list[dict]:
    return [h.model_dump(mode="json") for h in state.ip_hosts.values()]


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Canale bidirezionale di telemetria industriale in tempo reale.
    Effettua broadcast degli eventi: scan_progress, device_found, bus_health_update, log_record.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            await manager.handle_client_message(websocket, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        logger.error("WS error: %s", exc)
        manager.disconnect(websocket)


# ── Reports ───────────────────────────────────────────────────────────────────

@router.get(
    "/report/excel",
    tags=["reports"],
    response_class=FileResponse,
    summary="Download report as-built in formato Excel (8 fogli)",
    description="Genera e scarica al volo una cartella Excel stilizzata con 8 fogli di lavoro completi di topologia, inventario dispositivi e registri.",
)
async def export_excel():
    from reports.excel import generate_excel
    fd, tmp = tempfile.mkstemp(suffix=".xlsx", prefix="bham_report_")
    os.close(fd)
    generate_excel(tmp)
    return FileResponse(
        path=tmp,
        filename="bham_report.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        background=BackgroundTask(os.unlink, tmp),
    )


@router.get(
    "/report/pdf",
    tags=["reports"],
    response_class=FileResponse,
    summary="Download verbale di collaudo in formato PDF vettoriale",
    description="Genera e scarica il verbale tecnico as-built vettoriale a due passate con albero topologico gerarchico e tabelle perizie d'impianto.",
)
async def export_pdf():
    from reports.pdf import generate_pdf
    fd, tmp = tempfile.mkstemp(suffix=".pdf", prefix="bham_report_")
    os.close(fd)
    generate_pdf(tmp)
    return FileResponse(
        path=tmp,
        filename="bham_report.pdf",
        media_type="application/pdf",
        background=BackgroundTask(os.unlink, tmp),
    )


# ── Diagnostics ───────────────────────────────────────────────────────────────

@router.post(
    "/diag/modbus/fc43",
    tags=["diagnostics"],
    response_model=FC43Response,
    summary="Lettura Modbus FC43 Read Device Identification",
    description="Interroga lo slave specificato tramite Function Code 43 (0x2B) per estrarre VendorName, ProductCode e RevisionNumber.",
)
async def modbus_fc43(req: FC43Request) -> dict:
    from scanners.modbus import read_device_identification
    params = {"baudrate": req.baudrate, "parity": req.parity, "stopbits": req.stopbits}
    result = await read_device_identification(req.port, params, req.slave_id)
    return result


@router.get(
    "/diag/serial/health",
    tags=["diagnostics"],
    response_model=Optional[BusHealth],
    summary="Telemetria fisica della salute del bus RS485 (Bus Health)",
    description="Ritorna la qualità fisica del livello 1 RS485: Packet Error Rate %, Bus Load %, FPS, nodi attivi e diagnosi euristiche.",
)
async def get_serial_bus_health() -> Optional[dict]:
    return state.bus_health.model_dump(mode="json") if state.bus_health else None


# ── Setup & Hardware Discovery ────────────────────────────────────────────────

@router.get(
    "/setup/serial-ports",
    tags=["setup"],
    response_model=list[SerialPortInfo],
    summary="Elenca porte seriali disponibili (auto-scan)",
    description="Ritorna l'elenco delle porte seriali del sistema operativo con riconoscimento dei chip convertitori USB-RS485 noti.",
)
async def get_serial_ports() -> list[dict]:
    from core.hw_discovery import list_serial_ports
    return list_serial_ports()


@router.get(
    "/setup/network-interfaces",
    tags=["setup"],
    response_model=NetworkInterfacesResponse,
    summary="Elenca interfacce di rete attive con IP e porte di accesso",
    description="Ritorna schede di rete cablate ed Ethernet attive, con suggerimento single_iface_mode e IP LAN per controllo remoto.",
)
async def get_network_interfaces() -> dict:
    from core.hw_discovery import get_host_lan_ips, list_network_interfaces, suggest_single_iface
    ifaces = list_network_interfaces()
    return {
        "interfaces":       ifaces,
        "single_iface_mode": suggest_single_iface(ifaces),
        "lan_ips":          get_host_lan_ips(),
        "port":             settings.port,
    }


@router.get(
    "/network/oui/{mac}",
    tags=["setup"],
    response_model=OUILookupResponse,
    summary="Risolve il produttore/vendor dal MAC address",
    description="Interroga il database OUI IEEE integrato per identificare il produttore del controller o apparato di rete (es. Schneider Electric, Siemens, Carel, WAGO, Beckhoff, Moxa, Tridium).",
)
async def lookup_oui(mac: str) -> dict:
    from core.oui_lookup import format_mac_colon, get_vendor_by_mac
    vendor = get_vendor_by_mac(mac)
    return {
        "mac": format_mac_colon(mac),
        "vendor": vendor,
        "recognized": vendor is not None,
    }


@router.get(
    "/hardware/self-test",
    tags=["setup"],
    response_model=HardwareSelfTestResponse,
    summary="Collaudo diagnostico 1-click di interfacce e permessi (Self-Test)",
    description="Esegue in tempo reale il collaudo di apertura della porta seriale con latenza ms, verifica link schede di rete e privilegi OS (dialout, admin, Npcap).",
)
async def hardware_self_test(port: Optional[str] = None) -> dict:
    from core.hw_discovery import run_hardware_self_test
    return run_hardware_self_test(target_serial_port=port)


@router.post(
    "/setup/configure",
    tags=["setup"],
    response_model=ConfigureResponse,
    summary="Applica configurazione hardware alla sessione corrente",
    description="Memorizza i parametri di porta seriale, scheda di rete e nome impianto, avviando il file di log di sessione dedicato.",
)
async def configure_session(req: ConfigureRequest) -> dict:
    from core.logger import start_session_log
    from data.models import Parity, SessionConfig

    cfg = SessionConfig(
        serial_port=req.serial_port,
        serial_baudrate=req.serial_baudrate,
        serial_parity=Parity(req.serial_parity),
        serial_stopbits=req.serial_stopbits,
        scan_iface=req.scan_iface,
        scan_ip=req.scan_ip,
        client_iface=req.client_iface if not req.single_iface_mode else req.scan_iface,
        client_ip=req.client_ip if not req.single_iface_mode else req.scan_ip,
        single_iface_mode=req.single_iface_mode,
        site_name=req.site_name,
    )
    state.set_session_config(cfg)

    site = req.site_name or "sessione"
    start_session_log(site)

    logger.info(
        "Configurazione applicata: porta=%s scan_iface=%s client_iface=%s single=%s",
        cfg.serial_port, cfg.scan_iface, cfg.client_iface, cfg.single_iface_mode,
    )
    return {"configured": True, "config": cfg.model_dump(mode="json")}


@router.get(
    "/setup/config",
    tags=["setup"],
    response_model=ConfigActiveResponse,
    summary="Ritorna la configurazione hardware attiva",
    description="Recupera i parametri hardware correntemente applicati all'ambiente di collaudo.",
)
async def get_config() -> dict:
    if state.session_config is None:
        return {"configured": False, "config": None}
    return {"configured": True, "config": state.session_config.model_dump(mode="json")}


# ── Saved Sessions ────────────────────────────────────────────────────────────

@router.post(
    "/saved-sessions/save",
    tags=["saved-sessions"],
    response_model=SaveSessionResponse,
    summary="Salva snapshot della sessione corrente su disco",
    description="Crea uno snapshot JSON in sessions/ contenente configurazione, inventario dispositivi e percorso del log.",
)
async def save_current_session(req: SaveSessionRequest) -> dict:
    from core.logger import current_session_log_path
    from core.session_store import save_session

    cfg = state.session_config.model_dump(mode="json") if state.session_config else {}
    snap = state.snapshot()
    log_path = current_session_log_path()

    saved_path = save_session(
        name=req.name,
        config=cfg,
        state_snapshot=snap,
        log_path=log_path,
    )
    logger.info("Sessione '%s' salvata: %s", req.name, saved_path)
    return {"saved": True, "filename": saved_path.name}


@router.get(
    "/saved-sessions/list",
    tags=["saved-sessions"],
    response_model=list[SavedSessionMeta],
    summary="Lista delle sessioni salvate su disco",
    description="Elenca tutti i file di collaudo storici presenti nella directory sessions/ con contatori dispositivi e data.",
)
async def list_saved_sessions() -> list[dict]:
    from core.session_store import list_sessions as _list
    return _list()


@router.get(
    "/saved-sessions/{filename}",
    tags=["saved-sessions"],
    summary="Scarica il JSON completo di una sessione salvata",
    description="Restituisce il documento JSON integrale dello snapshot salvato su disco.",
)
async def get_saved_session(filename: str) -> dict:
    from core.session_store import load_session
    try:
        return load_session(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Sessione non trovata: {filename}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/saved-sessions/{filename}",
    tags=["saved-sessions"],
    response_model=DeleteSessionResponse,
    summary="Elimina definitivamente una sessione salvata",
    description="Rimuove il file JSON della sessione indicata dal disco.",
)
async def delete_saved_session(filename: str) -> dict:
    from core.session_store import delete_session
    try:
        delete_session(filename)
        return {"deleted": True, "filename": filename}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Sessione non trovata: {filename}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/saved-sessions/{filename}/restore",
    tags=["saved-sessions"],
    response_model=RestoreSessionResponse,
    summary="Ripristina una sessione salvata nello stato attivo",
    description="Carica i dispositivi e i canali della sessione salvata rimpiazzando lo stato attivo live corrente.",
)
async def restore_saved_session(filename: str) -> dict:
    from core.session_store import load_session
    try:
        data = load_session(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Sessione non trovata: {filename}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    results = data.get("results", {})
    if "session_config" not in results and data.get("config"):
        results["session_config"] = data["config"]

    state.restore_snapshot(results)
    logger.info("Sessione '%s' ripristinata nello stato attivo", filename)
    return {
        "restored": True,
        "filename": filename,
        "name": data.get("name", filename),
        "snapshot": state.snapshot(),
    }


@router.post(
    "/sessions/diff",
    tags=["saved-sessions"],
    response_model=SessionDiffResult,
    summary="Confronto differenziale (Prima vs Dopo) tra sessioni o stato live",
    description="Esegue il confronto analitico deterministico tra sessione baseline e sessione target per rilevare nodi aggiunti, rimossi, modificati o invariati.",
)
async def diff_sessions(req: SessionDiffRequest) -> dict:
    from core.session_store import load_session
    from core.session_diff import compare_snapshots

    try:
        base_data = load_session(req.baseline_filename)
        base_snapshot = base_data.get("results", {})
        base_name = base_data.get("name", req.baseline_filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Sessione baseline non trovata: {req.baseline_filename}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not req.target_filename or req.target_filename.lower() in ("live", "current", "__live__"):
        target_snapshot = state.snapshot()
        target_name = "Stato Attivo (Live)"
    else:
        try:
            target_data = load_session(req.target_filename)
            target_snapshot = target_data.get("results", {})
            target_name = target_data.get("name", req.target_filename)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Sessione target non trovata: {req.target_filename}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    result = compare_snapshots(
        baseline_snapshot=base_snapshot,
        target_snapshot=target_snapshot,
        baseline_name=base_name,
        target_name=target_name,
    )
    return result.model_dump(mode="json")


# ── BACS Help Maps ────────────────────────────────────────────────────────────

@router.post(
    "/maps/import",
    tags=["maps"],
    response_model=MapsImportResponse,
    summary="Importa definizioni mappa BACS Help (JSON)",
    description="Importa definizioni registri e punti per uno o più slave ID Modbus in formato compatibile BACS Help.",
)
async def import_maps(payload: Any = Body(...)) -> dict:
    from data.maps_manager import maps_manager
    imported = maps_manager.import_from_json(payload)
    return {"imported": imported, "total_slaves": len(maps_manager._maps)}


@router.get(
    "/maps/export",
    tags=["maps"],
    summary="Esporta tutte le mappe punti in formato JSON BACS Help",
    description="Esporta tutte le definizioni registri correntemente caricate in un unico documento JSON.",
)
async def export_maps() -> dict:
    from data.maps_manager import maps_manager
    return maps_manager.export_to_json()


@router.get(
    "/maps/{slave_id}",
    tags=["maps"],
    response_model=SlaveMapResponse,
    summary="Ritorna i punti mappati per uno slave ID specifico",
    description="Restituisce l'elenco dei punti registrati con offset, funzione Modbus, scala e descrizioni per lo slave indicato.",
)
async def get_slave_map(slave_id: int) -> dict:
    from data.maps_manager import maps_manager
    points = maps_manager.get_map(slave_id)
    if not points:
        raise HTTPException(status_code=404, detail=f"Nessuna mappa trovata per slave ID {slave_id}")
    return {
        "slave_id": slave_id,
        "point_count": len(points),
        "points": [p.to_dict() for p in points],
    }


# ── Modbus Smart Register Scan ────────────────────────────────────────────────

@router.post(
    "/modbus/smart-scan",
    tags=["modbus"],
    response_model=ModbusSmartScanResponse,
    summary="Esegue scansione euristica dei registri su uno slave",
    description="Interroga blocchi di registri Holding e Input dello slave, decodificando automaticamente numeri interi Int16/Int32, float IEEE 754 e stringhe ASCII.",
)
@router.post(
    "/scan/modbus/smart-scan",
    tags=["modbus"],
    response_model=ModbusSmartScanResponse,
    include_in_schema=False,
)
async def modbus_smart_scan(body: ModbusSmartScanBody) -> dict:
    from scanners.modbus import smart_register_scan
    port = body.port
    baudrate = body.baudrate
    parity = body.parity
    stopbits = body.stopbits
    ip = body.ip
    tcp_port = body.tcp_port

    if not ip and not port:
        with state._state_lock:
            for d in state.modbus_devices.values():
                if d.slave_id == body.slave_id:
                    if d.protocol == Protocol.MODBUS_TCP:
                        ip = d.ip
                        tcp_port = d.tcp_port
                    elif d.serial_params:
                        port = d.serial_params.port
                        baudrate = d.serial_params.baudrate
                        parity = d.serial_params.parity.value if hasattr(d.serial_params.parity, "value") else str(d.serial_params.parity)
                        stopbits = d.serial_params.stopbits
                    break

    return await smart_register_scan(
        slave_id=body.slave_id,
        port=port,
        baudrate=baudrate,
        parity=parity,
        stopbits=stopbits,
        ip=ip,
        tcp_port=tcp_port,
    )


# ── BACnet Object Explorer ────────────────────────────────────────────────────

@router.get(
    "/bacnet/devices/{device_id}/objects",
    tags=["bacnet"],
    response_model=BACnetObjectExplorerResponse,
    summary="Esplora gli oggetti BACnet di un dispositivo (GET)",
    description="Legge l'Object List del dispositivo BACnet specificato, enumerando oggetti analogici, binari, multistato, loop e schedule.",
)
@router.post(
    "/bacnet/devices/{device_id}/objects",
    tags=["bacnet"],
    response_model=BACnetObjectExplorerResponse,
    summary="Esplora gli oggetti BACnet di un dispositivo (POST)",
    description="Legge l'Object List permettendo di specificare l'indirizzo IP:porta esplicito dell'endpoint.",
)
async def get_bacnet_objects(device_id: int, address: Optional[str] = None) -> dict:
    from scanners.bacnet import explore_bacnet_objects
    return await explore_bacnet_objects(device_id=device_id, address=address)


# ── BBMD (BACnet Broadcast Management Device) Endpoints ───────────────────────

@router.get(
    "/bacnet/bbmd/tables",
    tags=["bacnet"],
    response_model=BBMDInfoResponse,
    summary="Interroga le tabelle BDT e FDT di un router BBMD",
    description="Legge contestualmente la Broadcast Distribution Table e la Foreign Device Table con countdown TTL da un router BBMD.",
)
async def get_bbmd_tables_endpoint(
    bbmd_ip: str = Query(..., description="Indirizzo IPv4 del router BBMD"),
    bbmd_port: int = Query(47808, description="Porta UDP del BBMD (default 47808)"),
    timeout: float = Query(3.0, description="Timeout richiesta in secondi"),
) -> dict:
    from scanners.bacnet import get_bbmd_tables
    return await get_bbmd_tables(bbmd_ip=bbmd_ip.strip(), bbmd_port=bbmd_port, timeout=timeout)


@router.get(
    "/bacnet/bbmd/bdt",
    tags=["bacnet"],
    response_model=list[BBDTEntry],
    summary="Legge la Broadcast Distribution Table (BDT) di un router BBMD",
    description="Restituisce le voci di instradamento broadcast configurate nel router BBMD.",
)
async def get_bbmd_bdt_endpoint(
    bbmd_ip: str = Query(..., description="Indirizzo IPv4 del router BBMD"),
    bbmd_port: int = Query(47808, description="Porta UDP del BBMD (default 47808)"),
    timeout: float = Query(3.0, description="Timeout richiesta in secondi"),
) -> list[dict]:
    from scanners.bacnet import read_bdt
    return await read_bdt(bbmd_ip=bbmd_ip.strip(), bbmd_port=bbmd_port, timeout=timeout)


@router.get(
    "/bacnet/bbmd/fdt",
    tags=["bacnet"],
    response_model=list[FDTEntry],
    summary="Legge la Foreign Device Table (FDT) di un router BBMD",
    description="Restituisce i dispositivi registrati come Foreign Device con tempo TTL rimanente.",
)
async def get_bbmd_fdt_endpoint(
    bbmd_ip: str = Query(..., description="Indirizzo IPv4 del router BBMD"),
    bbmd_port: int = Query(47808, description="Porta UDP del BBMD (default 47808)"),
    timeout: float = Query(3.0, description="Timeout richiesta in secondi"),
) -> list[dict]:
    from scanners.bacnet import read_fdt
    return await read_fdt(bbmd_ip=bbmd_ip.strip(), bbmd_port=bbmd_port, timeout=timeout)


# ── Strumenti di Campo: Banco Prova & Override ────────────────────────────────

@router.post(
    "/tools/modbus/read",
    tags=["modbus"],
    response_model=ModbusQuickReadResponse,
    summary="Modbus Quick Commander: Lettura Registri e Coils",
    description="Esegue la lettura immediata di registri o coil singoli/multipli (FC01, FC02, FC03, FC04) con decodifica Dec, Hex, Int16 e Float32.",
)
async def modbus_quick_read_endpoint(req: ModbusQuickReadRequest) -> dict:
    from scanners.field_tools import modbus_quick_read
    return await modbus_quick_read(
        protocol=req.protocol,
        port=req.port,
        baudrate=req.baudrate,
        parity=req.parity,
        stopbits=req.stopbits,
        ip=req.ip,
        tcp_port=req.tcp_port,
        slave_id=req.slave_id,
        function_code=req.function_code,
        address=req.address,
        count=req.count,
        timeout=req.timeout,
    )


@router.post(
    "/tools/modbus/write",
    tags=["modbus"],
    response_model=ModbusQuickWriteResponse,
    summary="Modbus Quick Commander: Scrittura e Forzatura",
    description="Forza registri o coils singoli/multipli (FC05, FC06, FC15, FC16) supportando valori interi, float IEEE-754 e bool.",
)
async def modbus_quick_write_endpoint(req: ModbusQuickWriteRequest) -> dict:
    from scanners.field_tools import modbus_quick_write
    return await modbus_quick_write(
        protocol=req.protocol,
        port=req.port,
        baudrate=req.baudrate,
        parity=req.parity,
        stopbits=req.stopbits,
        ip=req.ip,
        tcp_port=req.tcp_port,
        slave_id=req.slave_id,
        function_code=req.function_code,
        address=req.address,
        values=req.values,
        data_type=req.data_type,
        timeout=req.timeout,
    )


@router.post(
    "/tools/bacnet/write",
    tags=["bacnet"],
    response_model=BACnetPointOverrideResponse,
    summary="BACnet Point Commander: Forzatura temporanea presentValue",
    description="Forza il valore presentValue su oggetti BACnet con supporto al Priority Array (default Priorità 8: Operatore Manuale).",
)
async def bacnet_point_write_endpoint(req: BACnetPointOverrideRequest) -> dict:
    from scanners.field_tools import bacnet_point_override
    return await bacnet_point_override(
        device_id=req.device_id,
        address=req.address,
        object_type=req.object_type,
        instance=req.instance,
        value=req.value,
        priority=req.priority,
        relinquish=req.relinquish,
        timeout=req.timeout,
    )


@router.post(
    "/tools/bacnet/relinquish",
    tags=["bacnet"],
    response_model=BACnetPointOverrideResponse,
    summary="BACnet Point Commander: Rilascio Forzatura (Relinquish)",
    description="Rilascia la forzatura manuale (scrivendo NULL al Priority Array alla priorità specificata, default 8).",
)
async def bacnet_point_relinquish_endpoint(req: BACnetRelinquishRequest) -> dict:
    from scanners.field_tools import bacnet_point_override
    return await bacnet_point_override(
        device_id=req.device_id,
        address=req.address,
        object_type=req.object_type,
        instance=req.instance,
        value=None,
        priority=req.priority,
        relinquish=True,
        timeout=req.timeout,
    )


# ── Simulatore d'Impianto Virtuale (Demo / Offline Mode) ─────────────────────

@router.get(
    "/demo/status",
    tags=["system"],
    response_model=DemoStatusResponse,
    summary="Verifica stato Simulatore Virtuale (Demo Mode)",
    description="Restituisce lo stato attivo/inattivo del simulatore virtuale BACS e il conteggio dei dispositivi emulati.",
)
async def get_demo_status_endpoint() -> dict:
    from core.simulator import simulator
    return simulator.get_status()


@router.post(
    "/demo/toggle",
    tags=["system"],
    response_model=DemoToggleResponse,
    summary="Attiva o disattiva il Simulatore Virtuale",
    description="Inverte lo stato del simulatore virtuale (caricamento dispositivi o pulizia).",
)
async def toggle_demo_endpoint() -> dict:
    from core.simulator import simulator
    active = await simulator.toggle()
    msg = "Modalità Demo Attivata: caricati dispositivi virtuali Modbus, BACnet, KNX e ARP con telemetria sintetica." if active else "Modalità Demo Disattivata."
    return {"active": active, "message": msg}


@router.post(
    "/demo/enable",
    tags=["system"],
    response_model=DemoToggleResponse,
    summary="Attiva il Simulatore Virtuale",
)
async def enable_demo_endpoint() -> dict:
    from core.simulator import simulator
    await simulator.start()
    return {"active": True, "message": "Modalità Demo Attivata."}


@router.post(
    "/demo/disable",
    tags=["system"],
    response_model=DemoToggleResponse,
    summary="Disattiva il Simulatore Virtuale",
)
async def disable_demo_endpoint() -> dict:
    from core.simulator import simulator
    await simulator.stop()
    return {"active": False, "message": "Modalità Demo Disattivata."}


# ── Safe Mode Interlock ("Blocco Manovre & Sicurezza") ────────────────────────

@router.get(
    "/safe-mode/status",
    tags=["system"],
    response_model=SafeModeStatusResponse,
    summary="Stato del blocco Safe Mode per manovre di scrittura",
    description="Restituisce se il blocco manovre è armato (scrittura permessa) o sicuro (scrittura bloccata), con l'operatore e il countdown residuo.",
)
async def get_safe_mode_status_endpoint() -> dict:
    from core.safe_mode import safe_mode
    return safe_mode.get_status()


@router.post(
    "/safe-mode/arm",
    tags=["system"],
    response_model=SafeModeStatusResponse,
    summary="Sblocca Safe Mode per eseguire manovre di forzatura",
    description="Registra l'identità dell'operatore, il codice commessa e la finestra temporale autorizzata per le forzature di campo.",
)
async def arm_safe_mode_endpoint(req: SafeModeArmRequest) -> dict:
    from core.safe_mode import safe_mode
    try:
        return safe_mode.arm(
            operator=req.operator,
            job_order=req.job_order,
            duration_minutes=req.duration_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/safe-mode/disarm",
    tags=["system"],
    response_model=SafeModeStatusResponse,
    summary="Blocca immediatamente Safe Mode",
    description="Revoca tutte le autorizzazioni di scrittura e ripristina la modalità sicura di sola lettura.",
)
async def disarm_safe_mode_endpoint() -> dict:
    from core.safe_mode import safe_mode
    return safe_mode.disarm()


# ── Registro Manovre (Crash-Proof Audit Journal) ─────────────────────────────

@router.get(
    "/audit/journal",
    tags=["system"],
    response_model=list[AuditJournalEntry],
    summary="Registro Manovre Certificato: cronologia manovre di campo",
    description="Restituisce le ultime registrazioni del registro di audit append-only con hash SHA-256 concatenati.",
)
async def get_audit_journal_endpoint(
    limit: int = Query(100, description="Numero massimo di manovre da restituire (più recenti prima)")
) -> list[dict]:
    from core.audit_journal import audit_journal
    return audit_journal.list_entries(limit=limit, reverse=True)


@router.get(
    "/audit/verify",
    tags=["system"],
    response_model=AuditIntegrityResponse,
    summary="Verifica l'integrità crittografica del Registro Manovre",
    description="Ripercorre l'intera catena crittografica SHA-256 dal blocco di Genesi all'ultimo evento, certificando l'assenza di manomissioni o alterazioni di dati.",
)
async def verify_audit_journal_endpoint() -> dict:
    from core.audit_journal import audit_journal
    return audit_journal.verify_integrity()


@router.get(
    "/audit/export",
    tags=["system"],
    response_model=AuditExportResponse,
    summary="Esporta il Registro Manovre in formato JSON certificato",
    description="Genera il dump completo del registro manovre con sigillo di integrità crittografica per audit e perizia tecnica.",
)
async def export_audit_journal_endpoint() -> dict:
    import time
    from core.audit_journal import audit_journal
    integrity = audit_journal.verify_integrity()
    entries = audit_journal.list_entries(limit=10000, reverse=False)
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "valid": integrity["valid"],
        "total_entries": len(entries),
        "integrity": integrity,
        "entries": entries,
        "export_timestamp": now_iso,
    }


# ── Libreria Profili Modbus & Custom Profiles Manager ────────────────────────

@router.get(
    "/profiles",
    tags=["modbus"],
    response_model=list[ProfileMeta],
    summary="Libreria Profili Dispositivi Modbus",
    description="Elenca tutti i profili nativi di fabbrica (ABB, Gavazzi, IME, Schneider, Siemens, Belimo, Isoil, Diehl, Emerson, Carel, Riello, Trox) e custom utente.",
)
async def list_profiles_endpoint(
    category: Optional[str] = Query(None, description="Filtro opzionale categoria: multimeter, energy_heat, actuator_hvac, custom")
) -> list[dict]:
    from core.profile_manager import profile_manager
    return profile_manager.list_profiles(category=category)


@router.get(
    "/profiles/{profile_id}",
    tags=["modbus"],
    response_model=ProfileDetail,
    summary="Dettaglio completo di un profilo Modbus con mappa registri",
    description="Restituisce la definizione integrale di un profilo con elenco punti, indirizzi, tipi dato, unità ingegneristiche e scale.",
)
async def get_profile_endpoint(profile_id: str) -> dict:
    from core.profile_manager import profile_manager
    p = profile_manager.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Profilo '{profile_id}' non trovato.")
    return p


@router.post(
    "/profiles/custom",
    tags=["modbus"],
    response_model=ProfileDetail,
    summary="Crea o aggiorna un profilo Modbus personalizzato",
    description="Salva un profilo personalizzato definito dal tecnico nella cartella profili utente.",
)
async def create_custom_profile_endpoint(req: SaveCustomProfileRequest) -> dict:
    from core.profile_manager import profile_manager
    try:
        return profile_manager.save_custom_profile(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete(
    "/profiles/custom/{profile_id}",
    tags=["modbus"],
    summary="Elimina un profilo Modbus personalizzato",
    description="Rimuove il profilo utente specificato dal disco (i profili nativi di fabbrica sono protetti da scrittura).",
)
async def delete_custom_profile_endpoint(profile_id: str) -> dict:
    from core.profile_manager import profile_manager
    try:
        profile_manager.delete_custom_profile(profile_id)
        return {"deleted": True, "profile_id": profile_id}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Profilo '{profile_id}' non trovato.")
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post(
    "/profiles/apply",
    tags=["modbus"],
    response_model=ApplyProfileResponse,
    summary="Applica un profilo Modbus a uno slave attivo",
    description="Inietta automaticamente le definizioni di registri, scale e nomi del profilo sul dispositivo slave Modbus indicato.",
)
async def apply_profile_to_slave_endpoint(req: ApplyProfileRequest) -> dict:
    from core.profile_manager import profile_manager
    try:
        return profile_manager.apply_profile_to_slave(slave_id=req.slave_id, profile_id=req.profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


