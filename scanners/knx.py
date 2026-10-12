"""
BHAM – KNXnet/IP Scanner – Production Discovery Engine
======================================================
Pipeline KNXnet/IP Discovery:
1. Genera frame SEARCH_REQUEST (HPAI client endpoint)
2. Invia in multicast su 224.0.23.12:3671 e broadcast su LAN
3. Riceve e decodifica SEARCH_RESPONSE:
   - DIB Device Info: Indirizzo Individuale (Area.Linea.Device),
     Numero di Serie, Indirizzo MAC, Nome Dispositivo (30 byte ASCII),
     Medium di comunicazione (TP1, IP, RF, ecc.)
4. Upsert immediato su AppState e notifica WebSocket real-time.
"""

from __future__ import annotations

import asyncio
import socket
import struct
from typing import TYPE_CHECKING, Optional

from core.logger import logger
from data.models import KNXDevice, KNXTelegram, Protocol, ScanStatus
from data.state import state
from scanners.base import BaseScanner

if TYPE_CHECKING:
    from api.routes import KNXIPScanRequest

# ── Tunables ──────────────────────────────────────────────────────────────────
KNX_MULTICAST_GROUP = "224.0.23.12"
KNX_PORT            = 3671
SEARCH_TIMEOUT      = 3.5  # secondi finestra di ascolto

# Mappatura Medium KNX
MEDIUM_MAP = {
    0x01: "TP0",
    0x02: "TP1",
    0x04: "PL110",
    0x08: "PL132",
    0x10: "RF",
    0x20: "IP",
}


def _format_knx_address(raw_addr: int) -> str:
    """Formatta indirizzo individual a 16 bit in notazione Area.Linea.Device."""
    area = (raw_addr >> 12) & 0x0F
    line = (raw_addr >> 8) & 0x0F
    dev  = raw_addr & 0xFF
    return f"{area}.{line}.{dev}"


def format_knx_group_address(raw_addr: int) -> str:
    """Formatta indirizzo di gruppo a 16 bit in notazione 3-level standard: Main/Middle/Sub (es. 1/2/10)."""
    main = (raw_addr >> 11) & 0x1F
    middle = (raw_addr >> 8) & 0x07
    sub = raw_addr & 0xFF
    return f"{main}/{middle}/{sub}"


def decode_knx_dpt_value(apci_service: str, data: list[int] | bytes) -> tuple[Optional[str], Any, Optional[str]]:
    """
    Decodifica euristica dei valori dei payload KNX nei Datapoint Type (DPT) più diffusi:
    - DPT 1.001 (1-bit Bool / Switch: OFF/ON)
    - DPT 5.001 (8-bit Unsigned Scaling 0..100%)
    - DPT 6.001 (8-bit Signed -128..127)
    - DPT 9.001 (16-bit 2-octet Float: Temperatura °C, Pressione, ecc.)
    - DPT 14.xxx (32-bit 4-octet IEEE-754 Float standard)
    Ritorna: (dpt_guess, decoded_value, unit)
    """
    if apci_service == "GroupValueRead" or not data:
        return (None, None, None)

    b_data = bytes(data)
    length = len(b_data)

    if length == 1:
        val = b_data[0]
        if val in (0, 1):
            return ("DPT 1.001 (Switch)", bool(val), "ON" if val else "OFF")
        pct = round((val / 255.0) * 100, 1)
        return ("DPT 5.001 (Scaling 0-100%)", pct, "%")

    if length == 2:
        # KNX 2-octet float (DPT 9.xxx): [MEEEEMMM, MMMMMMMM]
        # bit 15: sign, bits 11..14: exp (0..15), bits 0..10: mantissa signed 11-bit
        raw16 = struct.unpack(">H", b_data)[0]
        sign = (raw16 >> 15) & 0x01
        exp = (raw16 >> 11) & 0x0F
        mantissa = raw16 & 0x07FF
        if sign == 1:
            mantissa = mantissa - 2048
        float_val = round((0.01 * mantissa) * (2 ** exp), 2)
        return ("DPT 9.001 (Temperatura)", float_val, "°C")

    if length == 4:
        try:
            f32 = round(struct.unpack(">f", b_data)[0], 3)
            return ("DPT 14.xxx (Float32)", f32, None)
        except Exception:
            u32 = struct.unpack(">I", b_data)[0]
            return ("DPT 12.001 (UInt32)", u32, None)

    try:
        txt = b_data.decode("latin-1").strip()
        if txt.isprintable() and len(txt) >= 2:
            return ("DPT 16.001 (String)", txt, None)
    except Exception:
        pass

    return ("Raw", b_data.hex(" ").upper(), None)


def parse_cemi_frame(data: bytes) -> Optional[KNXTelegram]:
    """
    Decodifica frame cEMI contenuto in un pacchetto KNXnet/IP Routing Indication (0x0530)
    o Tunneling Request (0x0420).
    """
    if len(data) < 10:
        return None

    # KNXnet/IP Header check
    hdr_len, version, service_type, total_len = struct.unpack(">BBHH", data[:6])
    if hdr_len != 0x06 or version != 0x10:
        return None

    cemi_offset = 6
    if service_type == 0x0530:
        cemi_offset = 6
    elif service_type == 0x0420:
        cemi_offset = 10
    else:
        return None

    if len(data) < cemi_offset + 10:
        return None

    cemi = data[cemi_offset:total_len]
    msg_code = cemi[0]
    # 0x11 = L_Data.ind, 0x29 = L_Data.con, 0x2B = L_Data.req
    if msg_code not in (0x11, 0x29, 0x2B):
        return None

    add_info_len = cemi[1]
    pos = 2 + add_info_len
    if len(cemi) < pos + 8:
        return None

    ctrl1 = cemi[pos]
    prio_code = (ctrl1 >> 2) & 0x03
    priority = {0: "system", 1: "urgent", 2: "normal", 3: "low"}.get(prio_code, "low")

    ctrl2 = cemi[pos + 1]
    dest_is_group = bool((ctrl2 >> 7) & 0x01)
    hop_count = (ctrl2 >> 4) & 0x07

    src_raw = struct.unpack(">H", cemi[pos + 2 : pos + 4])[0]
    dst_raw = struct.unpack(">H", cemi[pos + 4 : pos + 6])[0]
    src_addr_str = _format_knx_address(src_raw)
    dst_addr_str = format_knx_group_address(dst_raw) if dest_is_group else _format_knx_address(dst_raw)

    data_len = cemi[pos + 6]
    if len(cemi) < pos + 7 + data_len:
        return None

    tpci = cemi[pos + 7]
    apci_raw = cemi[pos + 8]
    apci_code = ((tpci & 0x03) << 8) | apci_raw

    apci_mask = apci_code & 0x03C0
    if apci_mask == 0x0000:
        service = "GroupValueRead"
    elif apci_mask == 0x0040:
        service = "GroupValueResponse"
    elif apci_mask == 0x0080:
        service = "GroupValueWrite"
    else:
        service = f"APCI_0x{apci_mask:04X}"

    payload_bytes: list[int] = []
    if data_len == 1:
        payload_bytes = [apci_raw & 0x3F]
    else:
        payload_bytes = list(cemi[pos + 9 : pos + 7 + data_len])

    raw_hex_str = " ".join(f"{b:02X}" for b in payload_bytes) if payload_bytes else ""
    dpt_guess, decoded_val, unit = decode_knx_dpt_value(service, payload_bytes)

    return KNXTelegram(
        source_address=src_addr_str,
        destination_group=dst_addr_str,
        service=service,
        raw_hex=raw_hex_str,
        data_bytes=payload_bytes,
        dpt_guess=dpt_guess,
        decoded_value=decoded_val,
        unit=unit,
        hop_count=hop_count,
        priority=priority,
    )


def _format_mac(raw_mac: bytes) -> str:
    """Formatta 6 byte in indirizzo MAC XX:XX:XX:XX:XX:XX."""
    return ":".join(f"{b:02x}" for b in raw_mac)


def _build_search_request(client_ip: str, client_port: int) -> bytes:
    """
    Costruisce pacchetto SEARCH_REQUEST conforme a standard KNXnet/IP:
    - Header: 0x06 (len), 0x10 (v1.0), 0x0201 (SEARCH_REQUEST), 0x000E (total len)
    - HPAI: 0x08 (len), 0x01 (UDP/IPv4), IP (4 byte), Port (2 byte)
    """
    header = struct.pack(">BBHH", 0x06, 0x10, 0x0201, 14)
    ip_parts = [int(p) for p in client_ip.split(".")] if client_ip and client_ip != "0.0.0.0" else [0, 0, 0, 0]
    hpai = struct.pack(">BBBBBBH", 0x08, 0x01, ip_parts[0], ip_parts[1], ip_parts[2], ip_parts[3], client_port)
    return header + hpai


def _parse_search_response(data: bytes, sender_addr: tuple[str, int]) -> Optional[KNXDevice]:
    """Decodifica un pacchetto SEARCH_RESPONSE KNXnet/IP (service 0x0202)."""
    if len(data) < 14:
        return None

    # Header check
    hdr_len, version, service_type, total_len = struct.unpack(">BBHH", data[:6])
    if hdr_len != 0x06 or version != 0x10 or service_type != 0x0202:
        return None

    # HPAI control endpoint (8 bytes da offset 6)
    hpai_len, hpai_proto = struct.unpack(">BB", data[6:8])
    if hpai_len != 0x08:
        return None

    offset = 6 + hpai_len

    # Parsing DIBs
    dev_name = ""
    knx_addr_str = "1.1.0"
    serial_str = ""
    mac_str = ""
    medium_str = "TP1"
    project_id = None

    while offset + 2 <= len(data):
        dib_len, dib_type = struct.unpack(">BB", data[offset:offset + 2])
        if dib_len == 0 or offset + dib_len > len(data):
            break

        dib_data = data[offset + 2:offset + dib_len]

        # DIB Type 0x01 = DEVICE_INFO
        if dib_type == 0x01 and len(dib_data) >= 52:
            medium_code = dib_data[0]
            medium_str = MEDIUM_MAP.get(medium_code, f"0x{medium_code:02x}")

            # Individual Address (offset 2..4 in dib_data)
            raw_knx_addr = struct.unpack(">H", dib_data[2:4])[0]
            knx_addr_str = _format_knx_address(raw_knx_addr)

            # Project install identifier
            project_id = struct.unpack(">H", dib_data[4:6])[0]

            # Serial number (6 bytes: offset 6..12)
            serial_bytes = dib_data[6:12]
            serial_str = serial_bytes.hex().upper()

            # MAC address (6 bytes: offset 16..22)
            mac_bytes = dib_data[16:22]
            mac_str = _format_mac(mac_bytes)

            # Friendly name (30 bytes: offset 22..52)
            name_raw = dib_data[22:52]
            dev_name = name_raw.split(b"\x00")[0].decode("latin-1", errors="replace").strip()

        offset += dib_len

    sender_ip, sender_port = sender_addr
    return KNXDevice(
        individual_address=knx_addr_str,
        device_name=dev_name or "KNXnet/IP Gateway",
        serial_number=serial_str or None,
        mac_address=mac_str or None,
        ip_address=sender_ip,
        port=sender_port,
        multicast_address=KNX_MULTICAST_GROUP,
        medium=medium_str,
        project_id=project_id,
    )


class KNXProtocol(asyncio.DatagramProtocol):
    """Protocollo UDP asyncio per ascolto risposte SEARCH_RESPONSE."""

    def __init__(self, scanner: KNXScanner) -> None:
        self.scanner = scanner
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            device = _parse_search_response(data, addr)
            if device:
                self.scanner.on_device_discovered(device)
        except Exception as exc:
            logger.debug("Errore parsing frame KNX da %s: %s", addr, exc)


class KNXScanner(BaseScanner):
    """Scanner KNXnet/IP asincrono multi-interfaccia."""

    def __init__(self, session_id: str) -> None:
        super().__init__(session_id)
        self._found: list[KNXDevice] = []

    def on_device_discovered(self, device: KNXDevice) -> None:
        """Callback su dispositivo rilevato."""
        # Evita duplicati nella stessa sessione
        if any(d.individual_address == device.individual_address and d.ip_address == device.ip_address for d in self._found):
            return

        self._found.append(device)
        state.upsert_knx(device)
        state.update_session(self.session_id, found_devices=len(self._found))
        logger.info(
            "KNX device trovato: %s @ %s (%s, SN: %s, MAC: %s)",
            device.individual_address, device.ip_address, device.device_name,
            device.serial_number, device.mac_address,
        )

    async def scan(self, req: KNXIPScanRequest) -> None:
        """Esegue broadcast/multicast di ricerca e raccoglie le risposte."""
        timeout = req.timeout if hasattr(req, "timeout") else SEARCH_TIMEOUT
        target_port = int(getattr(req, "port", KNX_PORT) or KNX_PORT)
        state.update_session(
            self.session_id,
            status=ScanStatus.RUNNING,
            progress_pct=10.0,
        )
        logger.info("Avvio discovery KNXnet/IP (porta: %d, timeout: %.1fs)...", target_port, timeout)

        loop = asyncio.get_running_loop()

        # Determina local IP per HPAI
        cfg = state.session_config
        local_ip = (cfg.scan_ip if cfg and cfg.scan_ip else "0.0.0.0")

        # Socket UDP bound a porta libera
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 16)
        except OSError:
            pass

        try:
            sock.bind((local_ip if local_ip != "0.0.0.0" else "", 0))
            bound_ip, bound_port = sock.getsockname()
            if bound_ip == "0.0.0.0" and local_ip != "0.0.0.0":
                bound_ip = local_ip
        except Exception:
            sock.bind(("", 0))
            bound_ip, bound_port = sock.getsockname()

        transport, protocol = await loop.create_datagram_endpoint(
            lambda: KNXProtocol(self),
            sock=sock,
        )

        try:
            # Crea e invia pacchetto SEARCH_REQUEST
            req_packet = _build_search_request(bound_ip, bound_port)

            # 1. Multicast su 224.0.23.12:target_port
            try:
                transport.sendto(req_packet, (KNX_MULTICAST_GROUP, target_port))
            except Exception as e:
                logger.debug("Invio multicast fallito: %s", e)

            # 2. Broadcast su 255.255.255.255:target_port (per router che non ascoltano multicast)
            try:
                transport.sendto(req_packet, ("255.255.255.255", target_port))
            except Exception:
                pass

            # Finestra di attesa con progress bar incrementale
            steps = 20
            step_dur = timeout / steps
            for i in range(steps):
                if self.is_aborted():
                    logger.warning("Scansione KNX interrotta da utente.")
                    state.finish_session(self.session_id, status=ScanStatus.ABORTED)
                    return
                await asyncio.sleep(step_dur)
                pct = 10.0 + (90.0 * (i + 1) / steps)
                state.update_session(self.session_id, progress_pct=pct)

            state.finish_session(self.session_id, status=ScanStatus.COMPLETED)
            logger.info("KNXnet/IP discovery completata: %d dispositivi trovati", len(self._found))

        except Exception as exc:
            logger.error("Errore durante KNXnet/IP discovery: %s", exc)
            state.update_session(self.session_id, errors=[str(exc)])
            state.finish_session(self.session_id, status=ScanStatus.ERROR)
        finally:
            try:
                transport.close()
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass


# ── KNX Group Monitor & Live Telegram Sniffer ─────────────────────────────────

class KNXGroupMonitorProtocol(asyncio.DatagramProtocol):
    """Protocollo UDP asyncio per intercettare frame di routing e tunneling cEMI."""

    def __init__(self, monitor: "KNXGroupMonitor") -> None:
        self.monitor = monitor

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            tg = parse_cemi_frame(data)
            if tg:
                state.record_knx_telegram(tg)
                logger.debug("KNX Telegram catturato: %s -> %s [%s] = %s", tg.source_address, tg.destination_group, tg.service, tg.decoded_value)
        except Exception as exc:
            logger.debug("Errore parsing frame KNX Group Monitor: %s", exc)


class KNXGroupMonitor:
    """
    Monitor continuo asincrono dei telegrammi KNXnet/IP.
    Ascolta in multicast su 224.0.23.12:3671 e supporta ricezione unicast.
    """

    def __init__(self) -> None:
        self._running: bool = False
        self._transport: Optional[asyncio.DatagramTransport] = None
        self._sock: Optional[socket.socket] = None

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self, port: int = KNX_PORT) -> bool:
        if self._running:
            return True

        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass

        # Multicast membership per 224.0.23.12
        try:
            mreq = struct.pack("4s4s", socket.inet_aton(KNX_MULTICAST_GROUP), socket.inet_aton("0.0.0.0"))
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception as exc:
            logger.debug("Impossibile impostare IP_ADD_MEMBERSHIP per KNX: %s", exc)

        try:
            sock.bind(("", port))
        except Exception:
            try:
                sock.bind(("", 0))
            except Exception as bind_err:
                logger.warning("Impossibile avviare socket KNX Group Monitor: %s", bind_err)
                sock.close()
                return False

        transport, _ = await loop.create_datagram_endpoint(
            lambda: KNXGroupMonitorProtocol(self),
            sock=sock,
        )
        self._sock = sock
        self._transport = transport
        self._running = True
        logger.info("KNX Group Monitor avviato in ascolto (multicast %s:%d)", KNX_MULTICAST_GROUP, port)
        return True

    async def stop(self) -> bool:
        if not self._running:
            return True
        self._running = False
        if self._transport:
            try:
                self._transport.close()
            except Exception:
                pass
            self._transport = None
        self._sock = None
        await asyncio.sleep(0.01)
        logger.info("KNX Group Monitor arrestato.")
        return True


knx_group_monitor = KNXGroupMonitor()
