"""
BHAM – REST API Routes
All HTTP endpoints. WebSocket endpoint lives here too for co-location.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.websockets import manager
from core.logger import logger
from data.models import Protocol
from data.state import state

router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "active_ws": len(manager._active)}


# ── State snapshot ────────────────────────────────────────────────────────────

@router.get("/state", tags=["data"])
async def get_state() -> dict:
    return state.snapshot()


@router.delete("/state", tags=["data"])
async def clear_state() -> dict:
    state.clear()
    return {"cleared": True}


# ── Sessions ──────────────────────────────────────────────────────────────────

@router.get("/sessions", tags=["scans"])
async def list_sessions() -> list[dict]:
    return [s.model_dump(mode="json") for s in state.sessions.values()]


@router.get("/sessions/{session_id}", tags=["scans"])
async def get_session(session_id: str) -> dict:
    session = state.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump(mode="json")


# ── Scan request models ───────────────────────────────────────────────────────

class ModbusRTUScanRequest(BaseModel):
    port: str
    baudrates: list[int] = [9600, 19200]
    parities: list[str] = ["N", "E"]
    stopbits: list[int] = [1]
    id_range: list[int] = list(range(1, 248))
    spy_ids: list[int] = [1, 2, 10]        # "Early Exit" sentinel IDs


class ModbusTCPScanRequest(BaseModel):
    hosts: list[str]                        # IP or CIDR
    tcp_port: int | str = 502               # Singola porta o stringa (es: "502", "502, 503")
    tcp_ports: list[int] = []               # Lista opzionale di porte intere esplicite
    unit_ids: list[int] = [1]


class BACnetIPScanRequest(BaseModel):
    iface: str = ""                         # empty = auto
    port: str | int = "47808"               # singolo port (47808), notazione BACx (BAC0, BAC1) o range (BAC0..BAC3)
    ports: list[int] = []                   # lista opzionale di porte intere esplicite


class KNXIPScanRequest(BaseModel):
    iface: str = ""
    port: int | str = 3671
    timeout: float = 3.5


class ARPSniffRequest(BaseModel):
    iface: str = ""
    duration: float = 30.0


class SerialSniffRequest(BaseModel):
    port: str
    baudrate: int = 0                       # 0 = auto-detect
    parity: str = "auto"                    # "auto", "N", "E", "O"
    stopbits: int = 1
    protocol_filter: str = "auto"           # "auto", "modbus_rtu", "bacnet_mstp"
    duration: float = 30.0                  # 0 = continuous until abort


# ── Scan trigger endpoints ────────────────────────────────────────────────────

@router.post("/scan/modbus/rtu", tags=["scans"])
async def start_modbus_rtu(req: ModbusRTUScanRequest) -> dict:
    from scanners.base import BaseScanner
    from scanners.modbus import ModbusScanner
    BaseScanner.reset_abort()
    session = state.new_session(Protocol.MODBUS_RTU, req.model_dump())
    scanner = ModbusScanner(session_id=session.id)
    asyncio.create_task(scanner.scan_rtu(req))
    return {"session_id": session.id, "status": "started"}


@router.post("/scan/serial/sniff", tags=["scans"])
async def start_serial_sniff(req: SerialSniffRequest) -> dict:
    from scanners.base import BaseScanner
    from scanners.serial_sniffer import SerialSniffer
    BaseScanner.reset_abort()
    proto = Protocol.MODBUS_RTU if req.protocol_filter == "modbus_rtu" else (
        Protocol.BACNET_MSTP if req.protocol_filter == "bacnet_mstp" else Protocol.UNKNOWN
    )
    session = state.new_session(proto, req.model_dump())
    sniffer = SerialSniffer(session_id=session.id)
    asyncio.create_task(sniffer.sniff(req))
    return {"session_id": session.id, "status": "started"}


@router.post("/scan/modbus/tcp", tags=["scans"])
async def start_modbus_tcp(req: ModbusTCPScanRequest) -> dict:
    from scanners.base import BaseScanner
    from scanners.modbus import ModbusScanner
    BaseScanner.reset_abort()
    session = state.new_session(Protocol.MODBUS_TCP, req.model_dump())
    scanner = ModbusScanner(session_id=session.id)
    asyncio.create_task(scanner.scan_tcp(req))
    return {"session_id": session.id, "status": "started"}


@router.post("/scan/bacnet/ip", tags=["scans"])
async def start_bacnet_ip(req: BACnetIPScanRequest) -> dict:
    from scanners.base import BaseScanner
    from scanners.bacnet import BACnetScanner
    BaseScanner.reset_abort()
    session = state.new_session(Protocol.BACNET_IP, req.model_dump())
    scanner = BACnetScanner(session_id=session.id)
    asyncio.create_task(scanner.scan_ip(req))
    return {"session_id": session.id, "status": "started"}


@router.post("/scan/knx/ip", tags=["scans"])
async def start_knx_ip(req: KNXIPScanRequest) -> dict:
    from scanners.base import BaseScanner
    from scanners.knx import KNXScanner
    BaseScanner.reset_abort()
    session = state.new_session(Protocol.KNX_IP, req.model_dump())
    scanner = KNXScanner(session_id=session.id)
    asyncio.create_task(scanner.scan(req))
    return {"session_id": session.id, "status": "started"}


@router.post("/scan/arp", tags=["scans"])
async def start_arp_sniff(req: ARPSniffRequest) -> dict:
    from scanners.base import BaseScanner
    from scanners.ip_sniffer import IPSniffer
    BaseScanner.reset_abort()
    session = state.new_session(Protocol.UNKNOWN, req.model_dump())
    sniffer = IPSniffer(session_id=session.id)
    asyncio.create_task(sniffer.sniff(req))
    return {"session_id": session.id, "status": "started"}


@router.post("/scan/abort", tags=["scans"])
async def abort_scan() -> dict:
    # Signal via a global abort event (scanner must check it)
    from scanners.base import abort_event
    abort_event.set()
    return {"aborted": True}


# ── Devices ───────────────────────────────────────────────────────────────────

@router.get("/devices/modbus", tags=["data"])
async def get_modbus_devices() -> list[dict]:
    return [d.model_dump(mode="json") for d in state.modbus_devices.values()]


@router.get("/devices/bacnet", tags=["data"])
async def get_bacnet_devices() -> list[dict]:
    return [d.model_dump(mode="json") for d in state.bacnet_devices.values()]


@router.get("/devices/knx", tags=["data"])
async def get_knx_devices() -> list[dict]:
    return [k.model_dump(mode="json") for k in state.knx_devices.values()]


@router.get("/devices/hosts", tags=["data"])
async def get_ip_hosts() -> list[dict]:
    return [h.model_dump(mode="json") for h in state.ip_hosts.values()]


# ── WebSocket ─────────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
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

@router.get("/report/excel", tags=["reports"],
            response_class=FileResponse,
            summary="Download discovery results as Excel")
async def export_excel():
    from reports.excel import generate_excel
    tmp = tempfile.mktemp(suffix=".xlsx", prefix="bham_report_")
    generate_excel(tmp)
    return FileResponse(
        path=tmp,
        filename="bham_report.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        background=None,
    )


@router.get("/report/pdf", tags=["reports"],
            response_class=FileResponse,
            summary="Download discovery results as PDF")
async def export_pdf():
    from reports.pdf import generate_pdf
    tmp = tempfile.mktemp(suffix=".pdf", prefix="bham_report_")
    generate_pdf(tmp)
    return FileResponse(
        path=tmp,
        filename="bham_report.pdf",
        media_type="application/pdf",
    )


# ── Modbus FC43 Device Identification ────────────────────────────────────────

class FC43Request(BaseModel):
    port: str
    baudrate: int = 9600
    parity: str = "N"
    stopbits: int = 1
    slave_id: int


@router.post("/diag/modbus/fc43", tags=["diagnostics"],
             summary="Read Modbus FC43 Device Identification from a slave")
async def modbus_fc43(req: FC43Request) -> dict:
    from scanners.modbus import read_device_identification
    params = {"baudrate": req.baudrate, "parity": req.parity, "stopbits": req.stopbits}
    result = await read_device_identification(req.port, params, req.slave_id)
    return result


@router.get("/diag/serial/health", tags=["diagnostics"],
            summary="Ottieni telemetria di salute del bus seriale (Bus Health)")
async def get_serial_bus_health() -> Optional[dict]:
    return state.bus_health.model_dump(mode="json") if state.bus_health else None


# ── Setup: Hardware Discovery ─────────────────────────────────────────────────

@router.get("/setup/serial-ports", tags=["setup"],
            summary="Elenca porte seriali disponibili (auto-scan)")
async def get_serial_ports() -> list[dict]:
    """Ritorna lista porte seriali con flag rs485_likely per i convertitori USB↔RS485."""
    from core.hw_discovery import list_serial_ports
    return list_serial_ports()


@router.get("/setup/network-interfaces", tags=["setup"],
            summary="Elenca interfacce di rete attive con IP")
async def get_network_interfaces() -> dict:
    """
    Ritorna NIC disponibili + suggerimento single_iface_mode.
    single_iface_mode=True → usa la stessa NIC per scan e client.
    """
    from core.hw_discovery import list_network_interfaces, suggest_single_iface
    ifaces = list_network_interfaces()
    return {
        "interfaces":       ifaces,
        "single_iface_mode": suggest_single_iface(ifaces),
    }


class ConfigureRequest(BaseModel):
    serial_port:       str | None = None
    serial_baudrate:   int = 9600
    serial_parity:     str = "N"
    serial_stopbits:   int = 1
    scan_iface:        str | None = None
    scan_ip:           str | None = None
    client_iface:      str | None = None
    client_ip:         str | None = None
    single_iface_mode: bool = False
    site_name:         str = ""


@router.post("/setup/configure", tags=["setup"],
             summary="Applica configurazione HW alla sessione corrente")
async def configure_session(req: ConfigureRequest) -> dict:
    """
    Salva la configurazione HW nello state e avvia il log di sessione dedicato.
    Broadcast WebSocket: evento 'config_updated'.
    """
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

    # Avvia log di sessione dedicato
    site = req.site_name or "sessione"
    start_session_log(site)

    logger.info(
        "Configurazione applicata: porta=%s scan_iface=%s client_iface=%s single=%s",
        cfg.serial_port, cfg.scan_iface, cfg.client_iface, cfg.single_iface_mode,
    )
    return {"configured": True, "config": cfg.model_dump(mode="json")}


@router.get("/setup/config", tags=["setup"],
            summary="Ritorna la configurazione HW attiva")
async def get_config() -> dict:
    if state.session_config is None:
        return {"configured": False}
    return {"configured": True, "config": state.session_config.model_dump(mode="json")}


# ── Saved Sessions ────────────────────────────────────────────────────────────

class SaveSessionRequest(BaseModel):
    name: str  # nome libero del tecnico


@router.post("/saved-sessions/save", tags=["saved-sessions"],
             summary="Salva snapshot della sessione corrente su disco")
async def save_current_session(req: SaveSessionRequest) -> dict:
    """
    Salva config + risultati + log correnti in sessions/<ts>_<name>.json.
    Non modifica lo state.
    """
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


@router.get("/saved-sessions/list", tags=["saved-sessions"],
            summary="Lista delle sessioni salvate su disco")
async def list_saved_sessions() -> list[dict]:
    from core.session_store import list_sessions as _list
    return _list()


@router.get("/saved-sessions/{filename}", tags=["saved-sessions"],
            summary="Scarica il JSON completo di una sessione salvata")
async def get_saved_session(filename: str) -> dict:
    from core.session_store import load_session
    try:
        return load_session(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Sessione non trovata: {filename}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/saved-sessions/{filename}", tags=["saved-sessions"],
               summary="Elimina una sessione salvata")
async def delete_saved_session(filename: str) -> dict:
    from core.session_store import delete_session
    try:
        delete_session(filename)
        return {"deleted": True, "filename": filename}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Sessione non trovata: {filename}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/saved-sessions/{filename}/restore", tags=["saved-sessions"],
             summary="Ripristina una sessione salvata nello stato attivo")
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


# ── BACS Help Maps ────────────────────────────────────────────────────────────

@router.post("/maps/import", tags=["maps"],
             summary="Importa definizioni mappa BACS Help (JSON)")
async def import_maps(payload: Any = Body(...)) -> dict:
    """
    Importa punti e registri per uno o più slave ID.
    Accetta formati compatibili BACS Help (array o dict con devices/points).
    """
    from data.maps_manager import maps_manager
    imported = maps_manager.import_from_json(payload)
    return {"imported": imported, "total_slaves": len(maps_manager._maps)}


@router.get("/maps/export", tags=["maps"],
            summary="Esporta tutte le mappe punti in formato JSON BACS Help")
async def export_maps() -> dict:
    from data.maps_manager import maps_manager
    return maps_manager.export_to_json()


@router.get("/maps/{slave_id}", tags=["maps"],
            summary="Ritorna i punti mappati per uno slave ID specifico")
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

