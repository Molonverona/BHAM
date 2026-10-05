"""
BHAM – BACS Advanced IP Scanner
Concurrent asynchronous subnet scanner with:
  - Rapid TCP/UDP & ARP ping sweep
  - MAC address discovery via OS ARP cache / L2
  - Manufacturer identification via IEEE OUI database
  - Multi-protocol hostname resolution (Reverse DNS PTR, NetBIOS Name Query)
  - Targeted BACS/IoT port scanner (502, 47808, 3671, 80, 443, 8080, 8443, 1911, 1883)
"""

from __future__ import annotations

import asyncio
import ipaddress
import platform
import re
import socket
import struct
import subprocess
import time
from typing import TYPE_CHECKING, Optional

from core.logger import logger
from core.oui_lookup import format_mac_colon, get_vendor_by_mac
from data.models import IPHost, Protocol, ScanStatus
from data.state import state
from scanners.base import BaseScanner

if TYPE_CHECKING:
    from api.schemas import IPScanRequest

_SYSTEM = platform.system()

# Porte industriali e servizi BACS / IoT
BACS_PORT_SERVICES: dict[int, tuple[str, Optional[Protocol]]] = {
    502: ("Modbus TCP", Protocol.MODBUS_TCP),
    47808: ("BACnet/IP", Protocol.BACNET_IP),
    3671: ("KNX/IP", Protocol.KNX_IP),
    80: ("HTTP (PLC/BMS Web)", None),
    443: ("HTTPS (Secure PLC/BMS)", None),
    8080: ("HTTP-Alt / Niagara Fox Web", None),
    8443: ("HTTPS-Alt / Niagara Fox Secure", None),
    1911: ("Niagara Fox Native", None),
    1883: ("MQTT Broker", None),
    8883: ("Secure MQTT", None),
    161: ("SNMP Agent", None),
}

# Regex per parsing output ARP
_ARP_LINUX_RE = re.compile(r"^(\d+\.\d+\.\d+\.\d+)\s+0x\w+\s+0x\w+\s+([0-9a-fA-F:]{17})")
_ARP_WIN_RE = re.compile(r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2}-[0-9a-fA-F]{2})")


def parse_target_ips(target: str) -> list[str]:
    """
    Estrae una lista ordinata di indirizzi IPv4 da una stringa CIDR (192.168.1.0/24),
    un range (192.168.1.1-192.168.1.50) o un singolo IP (192.168.1.10).
    Limita la dimensione massima a 1024 indirizzi per sicurezza operativa.
    """
    target = target.strip()
    if not target:
        return []

    # Caso 1: Range "192.168.1.10-192.168.1.30" oppure "192.168.1.10-30"
    if "-" in target:
        parts = target.split("-", 1)
        start_str = parts[0].strip()
        end_str = parts[1].strip()
        try:
            start_ip = ipaddress.IPv4Address(start_str)
            if "." in end_str:
                end_ip = ipaddress.IPv4Address(end_str)
            else:
                # Formato compatto es. 192.168.1.10-30
                base_prefix = str(start_ip).rsplit(".", 1)[0]
                end_ip = ipaddress.IPv4Address(f"{base_prefix}.{end_str}")

            if int(end_ip) < int(start_ip):
                start_ip, end_ip = end_ip, start_ip

            count = int(end_ip) - int(start_ip) + 1
            if count > 1024:
                count = 1024
            return [str(ipaddress.IPv4Address(int(start_ip) + i)) for i in range(count)]
        except Exception:
            pass

    # Caso 2: Notazione CIDR o Singolo IP
    try:
        if "/" in target:
            net = ipaddress.IPv4Network(target, strict=False)
            hosts = list(net.hosts())
            if not hosts:
                hosts = [net.network_address]
            if len(hosts) > 1024:
                hosts = hosts[:1024]
            return [str(h) for h in hosts]
        else:
            ip = ipaddress.IPv4Address(target)
            return [str(ip)]
    except Exception:
        return []


def read_os_arp_table() -> dict[str, str]:
    """
    Legge la tabella ARP corrente del sistema operativo senza privilegi speciali.
    Ritorna un dizionario {ip: mac}.
    """
    arp_map: dict[str, str] = {}
    if _SYSTEM == "Linux":
        # Tentativo 1: lettura diretta /proc/net/arp (molto veloce, <1ms)
        try:
            with open("/proc/net/arp", "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[1:]  # Salta header
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 4:
                        ip = parts[0]
                        mac = parts[3]
                        if mac != "00:00:00:00:00:00" and len(mac) == 17:
                            arp_map[ip] = format_mac_colon(mac)
            if arp_map:
                return arp_map
        except Exception:
            pass

    # Tentativo 2: comando 'arp -a' o 'ip neigh'
    try:
        cmd = ["arp", "-a"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
        out = res.stdout
        if _SYSTEM == "Windows":
            for match in _ARP_WIN_RE.finditer(out):
                ip, mac = match.group(1), match.group(2)
                arp_map[ip] = format_mac_colon(mac)
        else:
            for line in out.splitlines():
                # Formato tipico BSD/Linux arp -a: "? (192.168.1.1) at 00:11:22:33:44:55 [ether] on eth0"
                m = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-fA-F:]{17})", line)
                if m:
                    arp_map[m.group(1)] = format_mac_colon(m.group(2))
    except Exception:
        pass

    return arp_map


def query_netbios_name(ip: str, timeout_s: float = 0.5) -> Optional[str]:
    """
    Interroga l'host sulla porta UDP 137 (NetBIOS Name Service) con una richiesta NBSTAT (*).
    Molti PLC industriali, JACE Tridium e server BMS rispondono fornendo il nome host nativo.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout_s)
        # RFC 1002 - Node Status Request su nome wildcard "*"
        # TrnID (2B) + Flags (0x0000) + QDCOUNT (1) + ANCOUNT (0) + NSCOUNT (0) + ARCOUNT (0)
        # Question Name: CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA (32 bytes) + 0x00
        # Type: NBSTAT (0x0021) + Class: IN (0x0001)
        wildcard_name = b"\x20" + b"CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" + b"\x00"
        nbns_req = struct.pack(">HHHHHH", 0x1337, 0x0000, 1, 0, 0, 0) + wildcard_name + struct.pack(">HH", 0x0021, 0x0001)
        sock.sendto(nbns_req, (ip, 137))
        data, _ = sock.recvfrom(1024)
        sock.close()

        if len(data) > 56:
            # Numero di nomi NetBIOS ritornati
            num_names = data[56]
            if num_names > 0 and len(data) >= 57 + 18:
                # Il primo record contiene 15 byte di nome + 1 byte di tipo (padding spazi)
                raw_name = data[57:72].decode("ascii", errors="ignore").strip()
                if raw_name and not raw_name.startswith("IS~"):
                    return raw_name
    except Exception:
        pass
    return None


async def resolve_host_details(ip: str, timeout_s: float = 0.6) -> tuple[Optional[str], Optional[str]]:
    """
    Risolve il nome host provando in sequenza/parallelo:
    1. NetBIOS Name Query (UDP 137) - specifico per controllori d'impianto
    2. Reverse DNS (PTR query)
    Ritorna una tupla (hostname, fonte) es. ("JACE-8000", "netbios") oppure ("plc-ahu01.lan", "dns").
    """
    loop = asyncio.get_running_loop()

    # 1. Prova NetBIOS Name Query in thread separato
    try:
        nb_name = await loop.run_in_executor(None, query_netbios_name, ip, timeout_s)
        if nb_name:
            return nb_name, "netbios"
    except Exception:
        pass

    # 2. Prova Reverse DNS (PTR)
    try:
        ptr_name = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: socket.gethostbyaddr(ip)[0]),
            timeout=timeout_s,
        )
        if ptr_name and ptr_name != ip:
            return ptr_name, "dns"
    except Exception:
        pass

    return None, None


class IPScanner(BaseScanner):
    """
    Motore di scansione IP avanzato per reti BACS / IoT industriali.
    """

    async def scan(self, req: "IPScanRequest") -> None:  # type: ignore[override]
        log = logger.getChild("ip_scanner")
        state.update_session(self.session_id, status=ScanStatus.RUNNING, progress_pct=0.0)

        target_ips = parse_target_ips(req.subnet)
        total_ips = len(target_ips)
        if total_ips == 0:
            err_msg = f"Nessun indirizzo IP valido trovato nel parametro subnet: {req.subnet!r}"
            log.warning(err_msg)
            state.update_session(self.session_id, error_message=err_msg)
            state.finish_session(self.session_id, ScanStatus.ERROR)
            return

        log.info(
            "Avvio BACS IP Scanner – target=%s (%d IP), porte=%s, concorrenza=%d",
            req.subnet,
            total_ips,
            req.ports,
            req.concurrency,
        )

        ping_timeout_s = max(0.1, req.ping_timeout_ms / 1000.0)
        port_timeout_s = max(0.1, req.port_timeout_ms / 1000.0)
        sem = asyncio.Semaphore(req.concurrency)

        discovered_count = 0
        processed_count = 0

        async def _probe_single_port(ip: str, port: int) -> bool:
            """Tenta una connessione TCP non bloccante su una porta specifica."""
            try:
                connect_coro = asyncio.open_connection(ip, port)
                reader, writer = await asyncio.wait_for(connect_coro, timeout=port_timeout_s)
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                return True
            except (ConnectionRefusedError, ConnectionResetError):
                # Porta chiusa ma l'host È VIVO (ha risposto con RST)
                return False
            except Exception:
                return False

        async def _check_host_alive(ip: str) -> tuple[bool, Optional[float]]:
            """
            Verifica se l'host è raggiungibile provando a connettersi rapidamente
            a un sottoinsieme di porte industriali o standard (80, 443, 502, 47808, 137).
            Ritorna (is_alive, response_time_ms).
            """
            probe_ports = [p for p in req.ports if p in (80, 443, 502, 47808, 1911)]
            if not probe_ports:
                probe_ports = req.ports[:3] if req.ports else [80, 502]

            t0 = time.monotonic()
            for p in probe_ports:
                try:
                    connect_coro = asyncio.open_connection(ip, p)
                    reader, writer = await asyncio.wait_for(connect_coro, timeout=ping_timeout_s)
                    dt_ms = round((time.monotonic() - t0) * 1000.0, 1)
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except Exception:
                        pass
                    return True, dt_ms
                except (ConnectionRefusedError, ConnectionResetError):
                    # Host attivo che ha inviato TCP RST
                    dt_ms = round((time.monotonic() - t0) * 1000.0, 1)
                    return True, dt_ms
                except Exception:
                    continue

            return False, None

        async def _scan_ip_worker(ip: str) -> None:
            nonlocal discovered_count, processed_count
            if self.is_aborted():
                return

            async with sem:
                if self.is_aborted():
                    return

                is_alive, rtt_ms = await _check_host_alive(ip)

                # Se non ha risposto ai probe TCP, verifichiamo se è presente nella tabella ARP
                arp_cache = read_os_arp_table()
                cached_mac = arp_cache.get(ip)
                if cached_mac:
                    is_alive = True

                if is_alive:
                    open_ports: list[int] = []
                    services: dict[int, str] = {}
                    proto_hints: list[Protocol] = []

                    # Scansiona tutte le porte richieste per l'host identificato
                    for port in req.ports:
                        if self.is_aborted():
                            return
                        opened = await _probe_single_port(ip, port)
                        if opened:
                            open_ports.append(port)
                            svc_name, proto = BACS_PORT_SERVICES.get(port, (f"TCP/{port}", None))
                            services[port] = svc_name
                            if proto and proto not in proto_hints:
                                proto_hints.append(proto)

                    # Lookup MAC e Produttore OUI
                    mac = cached_mac or arp_cache.get(ip)
                    vendor = get_vendor_by_mac(mac) if mac else None

                    # Risoluzione Hostname (NetBIOS / Reverse DNS)
                    hostname = None
                    hostname_source = None
                    if req.resolve_names and not self.is_aborted():
                        hostname, hostname_source = await resolve_host_details(ip)

                    host = IPHost(
                        ip=ip,
                        mac=mac,
                        vendor=vendor,
                        hostname=hostname,
                        hostname_source=hostname_source,
                        open_ports=open_ports,
                        services=services,
                        response_time_ms=rtt_ms,
                        status="online",
                        protocol_hints=proto_hints,
                    )
                    state.upsert_ip_host(host)
                    discovered_count += 1
                    log.info(
                        "  ✓ IP Host trovato: %s | MAC: %s (%s) | Hostname: %s | Porte: %s",
                        ip,
                        mac or "sconosciuto",
                        vendor or "Generico",
                        hostname or "-",
                        open_ports or "-",
                    )

                processed_count += 1
                progress = round((processed_count / total_ips) * 100.0, 1)
                state.update_session(
                    self.session_id,
                    found_devices=discovered_count,
                    progress_pct=progress,
                )

        tasks = [asyncio.create_task(_scan_ip_worker(ip)) for ip in target_ips]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            log.info("Scansione IP annullata dall'utente.")
            state.finish_session(self.session_id, ScanStatus.ABORTED)
            return

        final_status = ScanStatus.ABORTED if self.is_aborted() else ScanStatus.COMPLETED
        state.update_session(self.session_id, found_devices=discovered_count, progress_pct=100.0)
        state.finish_session(self.session_id, final_status)
        log.info(
            "BACS IP Scanner completato – trovati %d host su %d IP scansionati.",
            discovered_count,
            total_ips,
        )
