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
from data.models import KNXDevice, Protocol, ScanStatus
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
