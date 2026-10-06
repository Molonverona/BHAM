"""
BHAM – API Request and Response Schemas
Contracts and Pydantic schemas for the REST API and OpenAPI documentation.
"""
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

from data.models import (
    BACnetDevice,
    BBDTEntry,
    BBMDInfoResponse,
    BusHealth,
    FDTEntry,
    IPHost,
    KNXDevice,
    ModbusDevice,
    Parity,
    Protocol,
    SavedSessionMeta,
    ScanSession,
    SessionConfig,
    SessionDiffRequest,
    SessionDiffResult,
)


# ── System & Health ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = Field("ok", description="Stato del demone BHAM")
    active_ws: int = Field(0, description="Numero di client WebSocket correntemente collegati")
    version: str = Field("", description="Versione attiva dell'applicazione")


class StateClearResponse(BaseModel):
    cleared: bool = Field(True, description="Conferma azzeramento della memoria di collaudo")


# ── Scan Requests ─────────────────────────────────────────────────────────────

class ModbusRTUScanRequest(BaseModel):
    port: str = Field(..., description="Dispositivo porta seriale (es. /dev/ttyUSB0 o COM3)")
    baudrates: list[int] = Field([9600, 19200], description="Lista velocità in baud da testare in sequenza")
    parities: list[str] = Field(["N", "E"], description="Lista parità da testare ('N', 'E', 'O')")
    stopbits: list[int] = Field([1], description="Stop bit ammessi")
    id_range: list[int] = Field(default_factory=lambda: list(range(1, 248)), description="Range di slave ID Modbus da sondare (1-247)")
    spy_ids: list[int] = Field([1, 2, 10], description="Sentinel IDs per Early Exit (se rispondono, il baudrate è confermato)")


class ModbusTCPScanRequest(BaseModel):
    hosts: list[str] = Field(..., description="Elenco di indirizzi IP singoli o subnet in notazione CIDR (es. 192.168.1.0/24)")
    tcp_port: int | str = Field(502, description="Porta o stringa di porte Modbus TCP (es. 502 o '502, 503')")
    tcp_ports: list[int] = Field(default_factory=list, description="Lista opzionale di porte intere esplicite")
    unit_ids: list[int] = Field([1], description="Elenco Unit ID Modbus TCP da interrogare per ciascun host")


class BACnetIPScanRequest(BaseModel):
    iface: str = Field("", description="Interfaccia di rete su cui inviare i broadcast (stringa vuota per auto-rilevamento)")
    port: str | int = Field("47808", description="Porta UDP o stringa BACx (es. 47808 o 'BAC0' o 'BAC0..BAC2')")
    ports: list[int] = Field(default_factory=list, description="Lista opzionale di porte intere esplicite")
    bbmd_ip: Optional[str] = Field(None, description="Indirizzo IPv4 del router BBMD per Foreign Device traversal")
    bbmd_port: int | str = Field(47808, description="Porta UDP del router BBMD (default 47808)")
    bbmd_ttl: int = Field(60, description="Time to Live in secondi per la registrazione Foreign Device")


class KNXIPScanRequest(BaseModel):
    iface: str = Field("", description="Interfaccia di rete locale per il socket multicast")
    port: int | str = Field(3671, description="Porta UDP KNXnet/IP (default standard 3671)")
    timeout: float = Field(3.5, description="Finestra temporale di ascolto risposte multicast in secondi")


class ARPSniffRequest(BaseModel):
    iface: str = Field("", description="Interfaccia di rete Ethernet per sniffing L2 raw socket")
    duration: float = Field(30.0, description="Durata della finestra di cattura passiva in secondi")


class IPScanRequest(BaseModel):
    subnet: str = Field(..., description="Sottorete CIDR (es. 192.168.1.0/24) o singolo IP / range IP")
    ports: list[int] = Field(
        default=[502, 47808, 3671, 80, 443, 8080, 8443, 1911, 1883],
        description="Lista porte TCP/UDP BACS e IoT da scansionare",
    )
    ping_timeout_ms: int = Field(400, description="Timeout probe host raggiungibile (ms)")
    port_timeout_ms: int = Field(500, description="Timeout connect porta TCP (ms)")
    resolve_names: bool = Field(True, description="Risoluzione automatica hostname (PTR, NetBIOS, mDNS)")
    concurrency: int = Field(50, description="Numero massimo di worker paralleli concorrenti")


class OUILookupResponse(BaseModel):
    mac: str
    vendor: Optional[str] = None
    recognized: bool = False


class SerialSniffRequest(BaseModel):
    port: str = Field(..., description="Porta seriale RS485 da monitorare (es. /dev/ttyUSB0)")
    baudrate: int = Field(0, description="Velocità in baud (0 = auto-baud tramite frequenza campionamento frame)")
    parity: str = Field("auto", description="Parità seriale ('auto', 'N', 'E', 'O')")
    stopbits: int = Field(1, description="Stop bit (1 o 2)")
    protocol_filter: str = Field("auto", description="Filtro decodifica: 'auto', 'modbus_rtu', 'bacnet_mstp'")
    duration: float = Field(30.0, description="Durata ascolto in secondi (0 = continuo fino ad Abort)")


# ── Scan Responses ────────────────────────────────────────────────────────────

class ScanActionResponse(BaseModel):
    session_id: str = Field(..., description="Identificativo univoco della sessione di scansione avviata")
    status: str = Field("started", description="Stato del task asincrono")


class ScanAbortResponse(BaseModel):
    aborted: bool = Field(True, description="Conferma ricezione del comando di stop")
    sessions: list[str] = Field(default_factory=list, description="Elenco ID delle sessioni terminate con successo")


class ScanAbortSingleResponse(BaseModel):
    aborted: bool = Field(True, description="Conferma arresto della sessione indicata")


# ── Hardware & Setup ──────────────────────────────────────────────────────────

class SerialPortInfo(BaseModel):
    port: str = Field(..., description="Percorso del device (es. /dev/ttyUSB0 o COM3)")
    description: str = Field("", description="Descrizione periferica dal driver OS")
    hwid: str = Field("", description="Identificativo hardware USB / PNP")
    vid: Optional[int] = Field(None, description="Vendor ID esadecimale convertitore")
    pid: Optional[int] = Field(None, description="Product ID esadecimale convertitore")
    rs485_likely: bool = Field(False, description="True se la periferica corrisponde a un chip RS485 noto (FTDI, CP210x, CH340, Prolific)")
    os_type: str = Field("linux", description="Piattaforma del sistema operativo ('linux' o 'windows')")


class NetworkInterfaceInfo(BaseModel):
    name: str = Field(..., description="Nome interfaccia di rete (es. eth0, wlan0, Ethernet)")
    ip: str = Field(..., description="Indirizzo IPv4 primario assegnato")
    netmask: str = Field("", description="Maschera di sottorete IPv4")
    is_up: bool = Field(True, description="Stato del link fisico")
    speed_mbps: int = Field(0, description="Velocità negoziata della scheda in Mbps")
    is_wireless: bool = Field(False, description="True se interfaccia Wi-Fi, False se cablata Ethernet")


class NetworkInterfacesResponse(BaseModel):
    interfaces: list[NetworkInterfaceInfo] = Field(default_factory=list, description="Schede di rete IPv4 attive rilevate")
    single_iface_mode: bool = Field(False, description="True se è consigliata una sola interfaccia per scansione e client web")
    lan_ips: list[str] = Field(default_factory=list, description="Indirizzi IPv4 LAN per accesso remoto da altri dispositivi")
    port: int = Field(8765, description="Porta HTTP del demone BHAM")


class HardwareSelfTestResponse(BaseModel):
    timestamp: float = Field(..., description="Timestamp epoch del collaudo")
    overall: str = Field(..., description="Stato complessivo hardware: 'ok', 'warning', 'error'")
    serial: dict[str, Any] = Field(..., description="Diagnosi porta seriale RS485 con latenza ms di apertura/chiusura")
    network: dict[str, Any] = Field(..., description="Diagnosi schede di rete e connettività")
    privileges: dict[str, Any] = Field(..., description="Diagnosi permessi OS (dialout, admin, cap_net_raw, Npcap)")


class ConfigureRequest(BaseModel):
    serial_port: Optional[str] = Field(None, description="Porta seriale RS485 selezionata")
    serial_baudrate: int = Field(9600, description="Velocità baud predefinita")
    serial_parity: str = Field("N", description="Parità predefinita ('N', 'E', 'O')")
    serial_stopbits: int = Field(1, description="Stop bit predefiniti")
    scan_iface: Optional[str] = Field(None, description="Nome scheda di rete per traffico scanner (es. eth0)")
    scan_ip: Optional[str] = Field(None, description="IP scheda scansione")
    client_iface: Optional[str] = Field(None, description="Nome scheda per interfaccia web client")
    client_ip: Optional[str] = Field(None, description="IP scheda client")
    single_iface_mode: bool = Field(False, description="Usa la stessa scheda di rete per scanner e interfaccia utente")
    site_name: str = Field("", description="Nome del sito o impianto del cliente")


class ConfigureResponse(BaseModel):
    configured: bool = Field(True, description="Conferma applicazione configurazione")
    config: SessionConfig = Field(..., description="Configurazione attiva")


class ConfigActiveResponse(BaseModel):
    configured: bool = Field(..., description="True se è presente una configurazione attiva salvata")
    config: Optional[SessionConfig] = Field(None, description="Configurazione attiva (se presente)")


# ── Saved Sessions ────────────────────────────────────────────────────────────

class SaveSessionRequest(BaseModel):
    name: str = Field(..., description="Nome descrittivo della sessione di collaudo assegnato dal tecnico")


class SaveSessionResponse(BaseModel):
    saved: bool = Field(True, description="Conferma salvataggio su disco")
    filename: str = Field(..., description="Nome del file JSON generato nella cartella sessions/")


class DeleteSessionResponse(BaseModel):
    deleted: bool = Field(True, description="Conferma eliminazione file")
    filename: str = Field(..., description="Nome del file rimosso")


class RestoreSessionResponse(BaseModel):
    restored: bool = Field(True, description="Conferma ripristino snapshot")
    filename: str = Field(..., description="Nome file della sessione ripristinata")
    name: str = Field(..., description="Nome sito o identificativo collaudo")
    snapshot: dict[str, Any] = Field(..., description="Stato completo dell'applicazione dopo il ripristino")


# ── Diagnostics & Modbus Smart Scan ──────────────────────────────────────────

class FC43Request(BaseModel):
    port: str = Field(..., description="Porta seriale RS485 del bus")
    baudrate: int = Field(9600, description="Velocità baud")
    parity: str = Field("N", description="Parità ('N', 'E', 'O')")
    stopbits: int = Field(1, description="Stop bit")
    slave_id: int = Field(..., description="Indirizzo slave Modbus da interrogare")


class FC43Response(BaseModel):
    model_config = {"protected_namespaces": ()}

    slave_id: int = Field(..., description="Indirizzo slave Modbus interrogato")
    supported: bool = Field(False, description="True se il dispositivo supporta FC43 MEI 0x0E")
    vendor_name: Optional[str] = Field(None, description="Nome costruttore")
    product_code: Optional[str] = Field(None, description="Codice prodotto")
    revision: Optional[str] = Field(None, description="Versione/Revisione firmware")
    vendor_url: Optional[str] = Field(None, description="URL costruttore")
    product_name: Optional[str] = Field(None, description="Nome prodotto esteso")
    model_name: Optional[str] = Field(None, description="Nome modello")
    user_application_name: Optional[str] = Field(None, description="Nome applicativo utente")
    error: Optional[str] = Field(None, description="Dettaglio eventuale errore di comunicazione")


class ModbusSmartScanBody(BaseModel):
    slave_id: int = Field(..., description="Indirizzo slave da scansionare")
    protocol: Optional[str] = Field("rtu", description="Protocollo di comunicazione: 'rtu' o 'tcp'")
    port: Optional[str] = Field(None, description="Porta seriale (per RTU)")
    baudrate: int = Field(9600, description="Velocità in baud")
    parity: str = Field("N", description="Parità")
    stopbits: int = Field(1, description="Stop bit")
    ip: Optional[str] = Field(None, description="Indirizzo IP host (per TCP)")
    tcp_port: int = Field(502, description="Porta TCP")


class ModbusSmartScanRegister(BaseModel):
    address: int = Field(..., description="Indirizzo del registro Modbus (0-based)")
    type: str = Field(..., description="Tipologia di registro: 'holding' o 'input'")
    raw_dec: int = Field(..., description="Valore grezzo decimale a 16 bit unsigned")
    raw_hex: str = Field(..., description="Valore grezzo in notazione esadecimale (es. 0x03E8)")
    int16: Optional[int] = Field(None, description="Decodifica intero signed a 16 bit (-32768..32767)")
    float32: Optional[float] = Field(None, description="Decodifica virgola mobile IEEE 754 a 32 bit")


class ModbusSmartScanResponse(BaseModel):
    slave_id: int = Field(..., description="Indirizzo slave Modbus interrogato")
    endpoint: Optional[str] = Field(None, description="Endpoint seriale o IP host utilizzato")
    elapsed_ms: Optional[float] = Field(None, description="Tempo impiegato per la scansione in millisecondi")
    found_count: Optional[int] = Field(0, description="Numero totale di registri attivi individuati")
    registers: list[ModbusSmartScanRegister] = Field(default_factory=list, description="Elenco dei registri rilevati")
    error: Optional[str] = Field(None, description="Eventuale messaggio di errore in caso di mancata connessione")


class BACnetObjectItem(BaseModel):
    identifier: str = Field(..., description="Identificativo tipo:istanza (es. analogInput:1)")
    type: str = Field(..., description="Tipo oggetto BACnet (es. analogInput, binaryValue)")
    instance: int = Field(..., description="Numero di istanza univoco dell'oggetto")
    name: str = Field(..., description="Nome descrittivo dell'oggetto (Object Name)")
    present_value: str = Field(..., description="Valore attuale letto sul campo (Present Value)")
    units: str = Field("", description="Unità di misura ingegneristica (es. °C, bar, %)")


class BACnetObjectExplorerResponse(BaseModel):
    device_id: int = Field(..., description="Device Instance ID BACnet")
    address: Optional[str] = Field(None, description="Indirizzo di rete del dispositivo (IP:porta)")
    count: Optional[int] = Field(0, description="Numero di oggetti enumerati")
    objects: list[BACnetObjectItem] = Field(default_factory=list, description="Elenco degli oggetti letti")
    error: Optional[str] = Field(None, description="Eventuale messaggio di errore se l'esplorazione è parziale o fallita")


# ── Mappe BACS Help ───────────────────────────────────────────────────────────

class MapsImportResponse(BaseModel):
    imported: int = Field(..., description="Numero di registri e punti importati con successo")
    total_slaves: int = Field(..., description="Totale slave con mappe caricate in memoria")


class SlaveMapResponse(BaseModel):
    slave_id: int = Field(..., description="Indirizzo slave Modbus")
    point_count: int = Field(..., description="Numero di punti definiti")
    points: list[dict[str, Any]] = Field(default_factory=list, description="Elenco punti con offset, tipo dato e descrizioni")


# ── Strumenti di Campo: Banco Prova & Override ────────────────────────────────

class ModbusQuickReadRequest(BaseModel):
    protocol: str = Field("rtu", description="Protocollo di comunicazione: 'rtu' o 'tcp'")
    port: Optional[str] = Field(None, description="Porta seriale RS485 (per RTU)")
    baudrate: int = Field(9600, description="Velocità baud")
    parity: str = Field("N", description="Parità ('N', 'E', 'O')")
    stopbits: int = Field(1, description="Stop bit (1 o 2)")
    ip: Optional[str] = Field(None, description="Indirizzo IP host (per TCP)")
    tcp_port: int = Field(502, description="Porta TCP")
    slave_id: int = Field(1, description="Indirizzo slave Modbus (1-247)")
    function_code: int = Field(3, description="Function Code: 1 (Coils), 2 (Discrete Inputs), 3 (Holding), 4 (Input)")
    address: int = Field(0, description="Indirizzo registro o coil (0-based)")
    count: int = Field(1, description="Numero di elementi consecutivi da leggere (1-125)")
    timeout: float = Field(0.8, description="Timeout lettura in secondi")


class ModbusQuickReadResponse(BaseModel):
    success: bool = Field(..., description="Esito della lettura")
    slave_id: Optional[int] = Field(None, description="Slave ID interrogato")
    function_code: Optional[int] = Field(None, description="Function Code utilizzato")
    address: Optional[int] = Field(None, description="Indirizzo base del registro")
    count: Optional[int] = Field(None, description="Numero di elementi letti")
    raw_values: list[Any] = Field(default_factory=list, description="Valori grezzi estratti dal bus")
    decoding: dict[str, Any] = Field(default_factory=dict, description="Decodifica immediata: raw_dec, raw_hex, int16, uint16, float32_be, float32_le")
    simulated: bool = Field(False, description="True se la lettura è stata servita dal simulatore d'impianto")
    elapsed_ms: float = Field(..., description="Latenza di esecuzione in millisecondi")
    error: Optional[str] = Field(None, description="Messaggio di errore in caso di fallimento")


class ModbusQuickWriteRequest(BaseModel):
    protocol: str = Field("rtu", description="Protocollo: 'rtu' o 'tcp'")
    port: Optional[str] = Field(None, description="Porta seriale RS485 (per RTU)")
    baudrate: int = Field(9600, description="Velocità baud")
    parity: str = Field("N", description="Parità ('N', 'E', 'O')")
    stopbits: int = Field(1, description="Stop bit (1 o 2)")
    ip: Optional[str] = Field(None, description="Indirizzo IP (per TCP)")
    tcp_port: int = Field(502, description="Porta TCP")
    slave_id: int = Field(1, description="Indirizzo slave Modbus (1-247)")
    function_code: int = Field(6, description="Function Code: 5 (Single Coil), 6 (Single Register), 15 (Multiple Coils), 16 (Multiple Regs)")
    address: int = Field(0, description="Indirizzo del registro o coil da forzare (0-based)")
    values: list[Any] = Field(default_factory=list, description="Valore/i da scrivere (interi, bool o float)")
    data_type: str = Field("uint16", description="Tipo dato sorgente: 'uint16', 'int16', 'float32', 'float32_swapped', 'bool'")
    timeout: float = Field(0.8, description="Timeout scrittura in secondi")


class ModbusQuickWriteResponse(BaseModel):
    success: bool = Field(..., description="Esito dell'operazione di forzatura")
    slave_id: Optional[int] = Field(None, description="Slave ID target")
    function_code: Optional[int] = Field(None, description="Function Code utilizzato")
    address: Optional[int] = Field(None, description="Indirizzo registro o coil scritto")
    written_values: list[Any] = Field(default_factory=list, description="Valori inviati sul bus")
    simulated: bool = Field(False, description="True se la forzatura ha aggiornato il simulatore virtuale")
    elapsed_ms: float = Field(..., description="Tempo impiegato in millisecondi")
    message: Optional[str] = Field(None, description="Messaggio esplicativo dell'azione eseguita")
    error: Optional[str] = Field(None, description="Dettaglio eventuale errore di comunicazione")


class BACnetPointOverrideRequest(BaseModel):
    device_id: int = Field(..., description="Device Instance ID target")
    address: Optional[str] = Field(None, description="Indirizzo IP:porta endpoint (opzionale, ricavato automaticamente se omesso)")
    object_type: str = Field(..., description="Tipo oggetto BACnet (es. analogOutput, binaryOutput, analogValue)")
    instance: int = Field(..., description="Numero di istanza dell'oggetto")
    value: Any = Field(None, description="Nuovo valore desiderato da forzare (float, int, bool o stringa)")
    priority: int = Field(8, description="Livello di priorità nel Priority Array (1..16, default 8: Manual Operator)")
    relinquish: bool = Field(False, description="Se True, rilascia l'override alla priorità indicata impostando il valore a NULL")
    timeout: float = Field(2.0, description="Timeout richiesta in secondi")


class BACnetPointOverrideResponse(BaseModel):
    success: bool = Field(..., description="Esito del comando di override o relinquish")
    device_id: int = Field(..., description="Device Instance ID target")
    object_identifier: str = Field(..., description="Identificativo oggetto (tipo:istanza)")
    value: Optional[str] = Field(None, description="Valore correntemente impostato (null se rilasciato)")
    priority: int = Field(..., description="Livello di priorità coinvolto (1..16)")
    relinquish: bool = Field(False, description="True se l'operazione ha rilasciato la priorità manuale")
    simulated: bool = Field(False, description="True se il comando ha modificato un dispositivo virtuale simulato")
    elapsed_ms: float = Field(..., description="Latenza di esecuzione in millisecondi")
    message: Optional[str] = Field(None, description="Conferma operativa dell'avvenuta forzatura")
    error: Optional[str] = Field(None, description="Dettaglio dell'errore in caso di fallimento")


class BACnetRelinquishRequest(BaseModel):
    device_id: int = Field(..., description="Device Instance ID target")
    address: Optional[str] = Field(None, description="Indirizzo IP:porta endpoint")
    object_type: str = Field(..., description="Tipo oggetto BACnet")
    instance: int = Field(..., description="Istanza dell'oggetto")
    priority: int = Field(8, description="Livello di priorità da rilasciare (default 8)")
    timeout: float = Field(2.0, description="Timeout richiesta in secondi")


# ── Simulatore Virtuale (Demo Mode) ───────────────────────────────────────────

class DemoStatusResponse(BaseModel):
    active: bool = Field(..., description="True se la modalità simulazione Demo è correntemente attiva")
    uptime_seconds: float = Field(..., description="Secondi trascorsi dall'avvio della simulazione")
    devices_count: int = Field(..., description="Numero di dispositivi virtuali attivi in memoria")
    summary: dict[str, Any] = Field(default_factory=dict, description="Riepilogo dispositivi per protocollo")


class DemoToggleResponse(BaseModel):
    active: bool = Field(..., description="Nuovo stato della modalità Demo (True=ON, False=OFF)")
    message: str = Field(..., description="Descrizione operativa dell'azione eseguita")


# ── Safe Mode Interlock ───────────────────────────────────────────────────────

class SafeModeStatusResponse(BaseModel):
    armed: bool = Field(..., description="True se il blocco manovre è disattivato e la scrittura è consentita")
    operator: str = Field("", description="Nome dell'operatore autorizzato")
    job_order: str = Field("", description="Codice commessa o identificativo impianto")
    armed_at: Optional[float] = Field(None, description="Timestamp sblocco autorizzazione")
    expires_at: Optional[float] = Field(None, description="Timestamp scadenza autorizzazione")
    remaining_seconds: int = Field(0, description="Secondi rimanenti prima del disarmo automatico")
    remaining_minutes: float = Field(0.0, description="Minuti rimanenti prima del blocco automatico")
    non_deactivatable: bool = Field(True, description="Garantisce che il blocco di sicurezza è permanente e non disattivabile globalmente")


class SafeModeArmRequest(BaseModel):
    operator: str = Field(..., description="Nome e cognome dell'operatore sul campo")
    job_order: str = Field(..., description="Numero di commessa / ordine di lavoro / ticket")
    duration_minutes: int = Field(30, description="Finestra temporale di sblocco in minuti (1..480, default 30)")


# ── Registro Manovre (Crash-Proof Audit Journal) ─────────────────────────────

class AuditJournalEntry(BaseModel):
    entry_id: str = Field(..., description="Identificativo univoco progressivo (es. JNL-000042)")
    timestamp_iso: str = Field(..., description="Data e ora UTC ISO-8601 dell'evento")
    timestamp_epoch: float = Field(..., description="Timestamp numerico ad alta precisione")
    phase: str = Field(..., description="Fase Write-Ahead: INTENT, RESULT o EVENT")
    action: str = Field(..., description="Azione eseguita (es. modbus_write_fc06, bacnet_override)")
    protocol: str = Field(..., description="Protocollo di campo coinvolto")
    operator: str = Field(..., description="Operatore responsabile registrato")
    job_order: str = Field(..., description="Commessa di riferimento")
    status: str = Field(..., description="Stato: pending, success, error, interrupted")
    prev_hash: str = Field(..., description="Hash crittografico SHA-256 della manovra precedente")
    entry_hash: str = Field(..., description="Hash crittografico SHA-256 sigillato della riga")
    intent_id: Optional[str] = Field(None, description="Riferimento all'ID intent per i record RESULT")
    target: Optional[dict[str, Any]] = Field(None, description="Coordinate nodo target (slave_id, registro, device_id)")
    value_requested: Optional[Any] = Field(None, description="Valore richiesto da forzare")
    value_verified: Optional[Any] = Field(None, description="Valore verificato sul bus con rilettura immediata")
    elapsed_ms: Optional[float] = Field(None, description="Tempo di risposta del dispositivo in ms")
    error: Optional[str] = Field(None, description="Eventuale eccezione o anomalia registrata")


class AuditIntegrityResponse(BaseModel):
    valid: bool = Field(..., description="True se l'intera catena crittografica è integra e non manomessa")
    total_entries: int = Field(..., description="Numero totale di registrazioni validate")
    genesis_hash: str = Field(..., description="Hash del blocco genesi")
    last_hash: str = Field(..., description="Hash dell'ultima registrazione sigillata")
    errors: list[str] = Field(default_factory=list, description="Eventuali violazioni di integrità o righe alterate")


class AuditExportResponse(BaseModel):
    valid: bool = Field(..., description="Esito verifica crittografica")
    total_entries: int = Field(..., description="Numero totale di manovre esportate")
    integrity: AuditIntegrityResponse = Field(..., description="Certificato di integrità hash chain")
    entries: list[dict[str, Any]] = Field(default_factory=list, description="Elenco manovre storiche")
    export_timestamp: str = Field(..., description="Data e ora generazione report certificato")


# ── Libreria Profili Modbus ──────────────────────────────────────────────────

class ProfilePoint(BaseModel):
    address: int = Field(..., description="Offset registro Modbus (0-based)")
    name: str = Field(..., description="Nome simbolico punto (es. V_L1_N, Active_Power)")
    type: str = Field("holding", description="Tipo registro: 'holding', 'input', 'coil', 'discrete'")
    format: str = Field("uint16", description="Formato dato: 'uint16', 'int16', 'uint32', 'int32', 'float32_be', 'float32_le', 'bool'")
    unit: str = Field("", description="Unità ingegneristica (es. V, A, kW, kWh, °C, m³/h)")
    scale: float = Field(1.0, description="Fattore moltiplicativo di scala (es. 0.1, 0.01)")
    access: str = Field("ro", description="Permessi accesso: 'ro' (sola lettura) o 'rw' (lettura/scrittura)")
    description: str = Field("", description="Descrizione tecnica estesa")


class ProfileMeta(BaseModel):
    id: str = Field(..., description="Identificativo univoco profilo (slug)")
    name: str = Field(..., description="Nome descrittivo commerciale del dispositivo")
    category: str = Field(..., description="Categoria: 'multimeter', 'energy_heat', 'actuator_hvac', 'custom'")
    manufacturer: str = Field("", description="Costruttore (es. ABB, Schneider, Belimo, IME, Siemens)")
    model: str = Field("", description="Modello del dispositivo")
    description: str = Field("", description="Descrizione funzionale")
    is_builtin: bool = Field(False, description="True se profilo nativo di fabbrica, False se custom utente")
    point_count: int = Field(..., description="Numero di registri definiti nel profilo")
    default_baudrate: int = Field(9600, description="Velocità baud tipica di fabbrica")
    default_parity: str = Field("N", description="Parità tipica di fabbrica ('N', 'E', 'O')")


class ProfileDetail(BaseModel):
    id: str = Field(..., description="Identificativo univoco profilo")
    name: str = Field(..., description="Nome dispositivo")
    category: str = Field(..., description="Categoria profilo")
    manufacturer: str = Field("", description="Costruttore")
    model: str = Field("", description="Modello")
    description: str = Field("", description="Descrizione")
    is_builtin: bool = Field(False, description="True se profilo nativo")
    default_baudrate: int = Field(9600, description="Velocità baud")
    default_parity: str = Field("N", description="Parità")
    default_stopbits: int = Field(1, description="Stop bit")
    points: list[ProfilePoint] = Field(default_factory=list, description="Registri e punti mappati")


class SaveCustomProfileRequest(BaseModel):
    id: Optional[str] = Field(None, description="ID profilo opzionale (generato automaticamente se omesso)")
    name: str = Field(..., description="Nome identificativo del profilo custom")
    category: str = Field("custom", description="Categoria ('multimeter', 'energy_heat', 'actuator_hvac', 'custom')")
    manufacturer: str = Field("", description="Produttore o costruttore")
    model: str = Field("", description="Modello o serie")
    description: str = Field("", description="Note descrittive")
    default_baudrate: int = Field(9600, description="Velocità baud")
    default_parity: str = Field("N", description="Parità")
    default_stopbits: int = Field(1, description="Stop bit")
    points: list[ProfilePoint] = Field(default_factory=list, description="Elenco registri da mappare")


class ApplyProfileRequest(BaseModel):
    slave_id: int = Field(..., description="Indirizzo slave Modbus target (1..247)")
    profile_id: str = Field(..., description="ID del profilo da applicare dalla libreria")


class ApplyProfileResponse(BaseModel):
    success: bool = Field(True, description="Esito applicazione profilo")
    slave_id: int = Field(..., description="Slave ID configurato")
    profile_id: str = Field(..., description="ID profilo applicato")
    profile_name: str = Field(..., description="Nome commerciale profilo")
    manufacturer: Optional[str] = Field(None, description="Costruttore applicato")
    mapped_points_count: int = Field(..., description="Numero di punti e registri applicati")
    points: list[dict[str, Any]] = Field(default_factory=list, description="Elenco punti mappati")


# ── Benchmark & Stress Test ───────────────────────────────────────────────────

class ModbusBenchmarkRequest(BaseModel):
    protocol: str = Field("rtu", description="'rtu' o 'tcp'")
    port: Optional[str] = Field(None, description="Dispositivo porta seriale (per RTU)")
    baudrate: int = Field(9600, description="Baudrate seriale")
    parity: str = Field("N", description="Parità ('N', 'E', 'O')")
    stopbits: int = Field(1, description="Stop bits")
    ip: Optional[str] = Field(None, description="Indirizzo IPv4 target (per TCP)")
    tcp_port: int = Field(502, description="Porta Modbus TCP")
    slave_id: int = Field(1, description="Slave ID o Unit ID da testare")
    address: int = Field(0, description="Offset registro di test")
    count: int = Field(1, description="Numero di registri per lettura")
    iterations: int = Field(20, description="Numero di campionamenti consecutivi (5..100)")
    timeout: float = Field(0.5, description="Timeout per singola richiesta (s)")


class ModbusBenchmarkResponse(BaseModel):
    success: bool = True
    protocol: str
    target: dict[str, Any]
    iterations: int
    success_count: int
    fail_count: int
    packet_error_rate_pct: float
    min_latency_ms: float
    max_latency_ms: float
    avg_latency_ms: float
    jitter_ms: float
    rating: str               # EXCELLENT, GOOD, DEGRADED, CRITICAL
    rating_label: str         # ECCELLENTE, BUONO, DEGRADATO, CRITICO
    diagnosis: str
    latencies: list[float]
    errors: list[str]
    total_elapsed_ms: float


# ── Commissioning Checklist ───────────────────────────────────────────────────

class DeviceCommissioningRequest(BaseModel):
    protocol: str = Field(..., description="'modbus', 'bacnet', 'knx', 'ip'")
    identifier: str = Field(..., description="Slave ID, Device ID, indirizzo o IP")
    status: str = Field(..., description="'ok', 'warning', 'failed', 'pending'")
    notes: Optional[str] = Field(None, description="Note tecniche di collaudo cantiere")
    commissioned_by: Optional[str] = Field(None, description="Nome del collaudatore")


class DeviceCommissioningResponse(BaseModel):
    success: bool = True
    protocol: str
    identifier: str
    status: str
    notes: Optional[str] = None
    commissioned_by: Optional[str] = None
    timestamp: str


# ── QR Code LAN Access ────────────────────────────────────────────────────────

class QRCodeResponse(BaseModel):
    url: str
    svg: str




