"""
BHAM – Pydantic Data Models
All domain entities used across scanners, API and reports.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    """Ritorna datetime corrente UTC compatibile con Python 3.12+."""
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────────────────────────

class Protocol(str, Enum):
    MODBUS_RTU = "modbus_rtu"
    MODBUS_TCP = "modbus_tcp"
    BACNET_IP  = "bacnet_ip"
    BACNET_MSTP = "bacnet_mstp"
    KNX_IP     = "knx_ip"
    UNKNOWN    = "unknown"


class ScanStatus(str, Enum):
    IDLE      = "idle"
    RUNNING   = "running"
    COMPLETED = "completed"
    ABORTED   = "aborted"
    ERROR     = "error"


class Parity(str, Enum):
    NONE = "N"
    EVEN = "E"
    ODD  = "O"


class FrameDirection(str, Enum):
    MASTER_TO_SLAVE = "master_to_slave"
    SLAVE_TO_MASTER = "slave_to_master"
    TOKEN           = "token"
    POLL            = "poll"
    BROADCAST       = "broadcast"
    UNKNOWN         = "unknown"


class SerialFrame(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    protocol: Protocol = Protocol.MODBUS_RTU
    direction: FrameDirection = FrameDirection.UNKNOWN
    source_addr: str = ""       # "M", slave ID o MS-TP MAC
    dest_addr: str = ""         # slave ID, broadcast o MS-TP MAC
    function_code: Optional[int] = None
    function_name: str = ""     # es. "FC03 Read Holding Registers", "Token (Type 0)"
    summary: str = ""           # descrizione leggibile per l'operatore
    raw_hex: str = ""           # rappresentazione esadecimale (es. "01 03 00 00 00 0A C5 CD")
    crc_ok: bool = True
    data: dict[str, Any] = Field(default_factory=dict)


class BusHealth(BaseModel):
    total_frames: int = 0
    valid_frames: int = 0
    crc_errors: int = 0
    packet_error_rate_pct: float = 0.0
    frames_per_sec: float = 0.0
    bus_load_pct: float = 0.0
    baudrate: int = 9600
    parity: str = "N"
    active_nodes: list[int] = Field(default_factory=list)
    physical_status: str = "GOOD"  # GOOD | WARNING | CRITICAL
    physical_diagnosis: Optional[str] = None


# ── Serial Parameters ────────────────────────────────────────────────────────

class SerialParams(BaseModel):
    port: str
    baudrate: int = 9600
    parity: Parity = Parity.NONE
    stopbits: int = 1
    bytesize: int = 8


# ── Device models ────────────────────────────────────────────────────────────

class ModbusDevice(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    slave_id: int
    protocol: Protocol = Protocol.MODBUS_RTU
    # Serial context (RTU)
    serial_params: Optional[SerialParams] = None
    # TCP context
    ip: Optional[str] = None
    tcp_port: int = 502
    # Meta
    discovered_at: datetime = Field(default_factory=utc_now)
    response_time_ms: Optional[float] = None
    registers: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    vendor_name: Optional[str] = None
    product_name: Optional[str] = None
    model_name: Optional[str] = None
    device_description: Optional[str] = None


class BACnetDevice(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    device_id: int
    protocol: Protocol = Protocol.BACNET_IP
    address: str                         # "192.168.1.10" or MS-TP MAC
    vendor_id: Optional[int] = None
    vendor_name: Optional[str] = None
    model_name: Optional[str] = None
    firmware_revision: Optional[str] = None
    application_software_version: Optional[str] = None
    object_list: list[dict[str, Any]] = Field(default_factory=list)
    bbmd_routed: bool = False
    routed_via: Optional[str] = None     # es. "192.168.10.1:47808"
    discovered_at: datetime = Field(default_factory=utc_now)
    tags: list[str] = Field(default_factory=list)


class KNXDevice(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    individual_address: str               # es. "1.1.0"
    device_name: Optional[str] = None     # es. "Gira KNX/IP Router"
    serial_number: Optional[str] = None   # es. "00C101234567"
    mac_address: Optional[str] = None
    ip_address: str
    port: int = 3671
    multicast_address: str = "224.0.23.12"
    medium: str = "TP1"                   # "TP1" | "IP" | "RF" | "PL110"
    project_id: Optional[int] = None
    discovered_at: datetime = Field(default_factory=utc_now)
    tags: list[str] = Field(default_factory=list)


class IPHost(BaseModel):
    ip: str
    mac: Optional[str] = None
    vendor: Optional[str] = None
    hostname: Optional[str] = None
    hostname_source: Optional[str] = None
    open_ports: list[int] = Field(default_factory=list)
    services: dict[int, str] = Field(default_factory=dict)
    response_time_ms: Optional[float] = None
    status: str = "online"
    first_seen: datetime = Field(default_factory=utc_now)
    last_seen: datetime = Field(default_factory=utc_now)
    protocol_hints: list[Protocol] = Field(default_factory=list)


# ── Scan Session ─────────────────────────────────────────────────────────────

class ScanSession(BaseModel):
    id: str
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: Optional[datetime] = None
    status: ScanStatus = ScanStatus.IDLE
    protocol: Protocol
    parameters: dict[str, Any] = Field(default_factory=dict)
    found_devices: int = 0
    errors: list[str] = Field(default_factory=list)
    progress_pct: float = 0.0
    error_message: Optional[str] = None   # human-readable error (e.g. permission denied)

# ── Hardware Discovery ────────────────────────────────────────────────────────

class SerialPortInfo(BaseModel):
    """Porta seriale rilevata da hw_discovery."""
    port:         str
    description:  str = ""
    hwid:         str = ""
    vid:          Optional[int] = None
    pid:          Optional[int] = None
    rs485_likely: bool = False
    os_type:      str = "linux"  # "linux" | "windows"


class NetworkInterface(BaseModel):
    """Interfaccia di rete attiva rilevata da hw_discovery."""
    name:        str
    ip:          str
    netmask:     str = ""
    is_up:       bool = True
    speed_mbps:  int = 0
    is_wireless: bool = False


# ── Session Configuration ─────────────────────────────────────────────────────

class SessionConfig(BaseModel):
    """Configurazione hardware attiva per la sessione corrente."""
    # Seriale RS485
    serial_port:       Optional[str] = None   # es. /dev/ttyUSB0 | COM3
    serial_baudrate:   int = 9600
    serial_parity:     Parity = Parity.NONE
    serial_stopbits:   int = 1

    # Rete
    scan_iface:        Optional[str] = None   # nome NIC per la scansione
    scan_ip:           Optional[str] = None
    client_iface:      Optional[str] = None   # nome NIC per connessione software
    client_ip:         Optional[str] = None
    single_iface_mode: bool = False           # True = scan e client sulla stessa NIC

    # Metadati sessione
    site_name:         str = ""               # nome del sito/cliente (usato per il salvataggio)
    configured_at:     Optional[datetime] = None

    @field_validator("configured_at", mode="before")
    @classmethod
    def _set_now(cls, v: Any) -> Any:
        return v or utc_now()


# ── Saved Session Metadata ────────────────────────────────────────────────────

class SavedSessionMeta(BaseModel):
    """Metadati di un profilo sessione salvato su disco (usato nella lista)."""
    filename:      str
    name:          str
    saved_at:      str
    has_log:       bool = False
    size_bytes:    int = 0
    device_counts: dict[str, int] = Field(default_factory=dict)


# ── Session Diff Models ───────────────────────────────────────────────────────

class DiffStatus(str, Enum):
    ADDED     = "added"       # Nuovo dispositivo rispetto a baseline
    REMOVED   = "removed"     # Dispositivo presente in baseline ma assente/offline
    MODIFIED  = "modified"    # Dispositivo con parametri modificati
    UNCHANGED = "unchanged"   # Dispositivo identico


class FieldChange(BaseModel):
    """Singola variazione rilevata su un campo/parametro del dispositivo."""
    field:       str
    baseline:    Any = None
    target:      Any = None
    description: str = ""


class DeviceDiffItem(BaseModel):
    """Elemento differenziale analitico per un dispositivo."""
    protocol:      str            # "modbus", "bacnet", "knx", "ip_host"
    identifier:    str            # "Slave 1", "Device 1234", "1.1.0", "192.168.1.10"
    label:         str            # Descrizione sintetica leggibile
    status:        DiffStatus
    baseline_data: Optional[dict[str, Any]] = None
    target_data:   Optional[dict[str, Any]] = None
    changes:       list[FieldChange] = Field(default_factory=list)


class ProtocolDiffSummary(BaseModel):
    """Conteggi di sintesi per protocollo o aggregati."""
    added:          int = 0
    removed:        int = 0
    modified:       int = 0
    unchanged:      int = 0
    total_baseline: int = 0
    total_target:   int = 0


class SessionDiffResult(BaseModel):
    """Risultato completo del confronto differenziale tra due sessioni."""
    baseline_name: str
    target_name:   str
    compared_at:   datetime = Field(default_factory=utc_now)
    summary:       dict[str, ProtocolDiffSummary] = Field(default_factory=dict)
    items:         list[DeviceDiffItem] = Field(default_factory=list)


class SessionDiffRequest(BaseModel):
    """Richiesta di confronto differenziale."""
    baseline_filename: str
    target_filename:   Optional[str] = None   # None o 'live' = AppState corrente


# ── BBMD (BACnet Broadcast Management Device) Models ─────────────────────────

class BBDTEntry(BaseModel):
    """Singola voce della Broadcast Distribution Table (BDT) di un BBMD."""
    ip: str
    port: int = 47808
    broadcast_mask: str = "255.255.255.255"


class FDTEntry(BaseModel):
    """Singola voce della Foreign Device Table (FDT) di un BBMD."""
    ip: str
    port: int = 47808
    ttl: int = 60
    remaining_time: int = 60


class BBMDInfoResponse(BaseModel):
    """Tabelle BDT e FDT lette da un router BBMD."""
    bbmd_ip: str
    bbmd_port: int = 47808
    bdt: list[BBDTEntry] = Field(default_factory=list)
    fdt: list[FDTEntry] = Field(default_factory=list)
    error: Optional[str] = None


