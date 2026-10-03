"""
BHAM – Hardware Discovery
Auto-scan seriale RS485 e interfacce di rete disponibili.
Cross-platform: Linux (/dev/ttyUSBx) e Windows (COMx).
"""

from __future__ import annotations

import logging
import platform
from typing import Optional

log = logging.getLogger("bham").getChild("hw_discovery")

# ── VID noti per convertitori USB↔RS485 ─────────────────────────────────────
_RS485_VID_PID: set[tuple[int, Optional[int]]] = {
    (0x0403, None),   # FTDI (FT232, FT485, FT2232, …)
    (0x1A86, 0x7523), # CH340
    (0x1A86, 0x7522), # CH341
    (0x10C4, 0xEA60), # Silicon Labs CP2102
    (0x10C4, 0xEA61), # Silicon Labs CP2104
    (0x067B, 0x2303), # Prolific PL2303
    (0x067B, 0x23A3), # Prolific PL2303GC
    (0x04D8, 0x000A), # Microchip USB-UART
    (0x2C7C, 0x0125), # Quectel EC25 (RS485 board)
}

_RS485_KEYWORDS = ("rs485", "rs-485", "rs232", "uart", "serial", "ftdi",
                   "ch340", "ch341", "cp210", "prolific", "pl2303")


def _is_rs485_likely(port_info) -> bool:
    """True se la porta sembra un convertitore USB↔RS485 (VID/PID o descrizione)."""
    try:
        vid = port_info.vid
        pid = port_info.pid
        if vid is not None:
            for known_vid, known_pid in _RS485_VID_PID:
                if vid == known_vid and (known_pid is None or pid == known_pid):
                    return True
    except AttributeError:
        pass
    desc  = (port_info.description or "").lower()
    hwid  = (port_info.hwid or "").lower()
    return any(kw in f"{desc} {hwid}" for kw in _RS485_KEYWORDS)


def list_serial_ports() -> list[dict]:
    """
    Elenca tutte le porte seriali disponibili.

    Returns:
        Lista di dict: port, description, hwid, vid, pid, rs485_likely, os_type.
    """
    try:
        from serial.tools.list_ports import comports  # type: ignore
    except ImportError:
        log.warning("pyserial non disponibile – impossibile listare porte seriali")
        return []

    os_type = "windows" if platform.system() == "Windows" else "linux"
    result: list[dict] = []

    for p in comports():
        entry = {
            "port":         p.device,
            "description":  p.description or "",
            "hwid":         p.hwid or "",
            "vid":          p.vid,
            "pid":          p.pid,
            "rs485_likely": _is_rs485_likely(p),
            "os_type":      os_type,
        }
        result.append(entry)
        log.debug("Porta seriale: %s [%s] rs485=%s", p.device, p.description, entry["rs485_likely"])

    log.info("Porte seriali rilevate: %d (RS485-likely: %d)",
             len(result), sum(1 for e in result if e["rs485_likely"]))
    return result


def list_network_interfaces() -> list[dict]:
    """
    Elenca interfacce di rete IPv4 attive (esclude loopback e link-local).

    Returns:
        Lista di dict: name, ip, netmask, is_up, speed_mbps, is_wireless.
    """
    try:
        import psutil  # type: ignore
    except ImportError:
        log.warning("psutil non disponibile – impossibile listare NIC")
        return []

    addrs   = psutil.net_if_addrs()
    stats   = psutil.net_if_stats()
    AF_INET = 2  # socket.AF_INET

    result: list[dict] = []

    for name, addr_list in addrs.items():
        iface_stats = stats.get(name)
        if not iface_stats or not iface_stats.isup:
            continue

        for addr in addr_list:
            if addr.family != AF_INET:
                continue
            ip = addr.address or ""
            if not ip or ip.startswith("127.") or ip.startswith("169.254."):
                continue

            lower = name.lower()
            is_wireless = any(tok in lower for tok in ("wl", "wifi", "wlan"))

            entry = {
                "name":        name,
                "ip":          ip,
                "netmask":     addr.netmask or "",
                "is_up":       True,
                "speed_mbps":  iface_stats.speed,
                "is_wireless": is_wireless,
            }
            result.append(entry)
            log.debug("NIC: %s ip=%s speed=%dMbps wireless=%s",
                      name, ip, iface_stats.speed, is_wireless)

    log.info("Interfacce di rete attive: %d", len(result))
    return result


def suggest_single_iface(ifaces: list[dict]) -> bool:
    """
    True se è ragionevole usare una sola interfaccia per scan + client.
    Condizione: esattamente 1 NIC cablata attiva con IP valido.
    """
    wired = [i for i in ifaces if not i.get("is_wireless")]
    single = len(wired) == 1
    if single:
        log.info("Single-iface mode suggerito: %s – %s", wired[0]["name"], wired[0]["ip"])
    return single


def run_hardware_self_test(target_serial_port: Optional[str] = None) -> dict:
    """
    Esegue un collaudo diagnostico istantaneo di tutto l'hardware e permessi di sistema.
    Non lancia scansioni invasive: verifica apertura porte, link NIC e privilegi OS.
    """
    from core.priv_check import check_privileges
    import time

    os_type = "windows" if platform.system() == "Windows" else "linux"
    priv = check_privileges()

    # 1. Test Porta Seriale RS485
    ports = list_serial_ports()
    rs485_likely = [p["port"] for p in ports if p.get("rs485_likely")]
    if target_serial_port:
        port_to_test = target_serial_port
    elif rs485_likely:
        port_to_test = rs485_likely[0]
    elif os_type == "windows" and ports:
        port_to_test = ports[0]["port"]
    else:
        port_to_test = None

    serial_res = {
        "tested_port": port_to_test,
        "available_ports": [p["port"] for p in ports],
        "status": "warning",  # ok | warning | error
        "message": "Nessun convertitore USB-RS485 rilevato (collega un adattatore FTDI, CH340, CP210x o Prolific).",
        "rs485_likely": False,
    }

    if port_to_test:
        matching = next((p for p in ports if p["port"] == port_to_test), None)
        serial_res["rs485_likely"] = matching.get("rs485_likely", False) if matching else False
        try:
            import serial
            t0 = time.monotonic()
            ser = serial.Serial(port=port_to_test, baudrate=9600, timeout=0.1)
            ser.close()
            ms = round((time.monotonic() - t0) * 1000, 1)
            serial_res["status"] = "ok"
            desc = matching.get("description", "") if matching else ""
            serial_res["message"] = f"Porta {port_to_test} operativa e accessibile ({desc}, {ms}ms)."
        except PermissionError as exc:
            serial_res["status"] = "error"
            if os_type == "windows":
                serial_res["message"] = f"Accesso negato a {port_to_test}: riesegui come Amministratore."
            else:
                serial_res["message"] = f"Permesso negato su {port_to_test}: aggiungi l'utente al gruppo dialout."
        except Exception as exc:
            serial_res["status"] = "error"
            serial_res["message"] = f"Impossibile aprire {port_to_test}: {exc}"

    # 2. Test Interfacce di Rete (NIC)
    nics = list_network_interfaces()
    wired = [n for n in nics if not n.get("is_wireless")]
    wireless = [n for n in nics if n.get("is_wireless")]

    if not nics:
        nic_status = "error"
        nic_msg = "Nessuna interfaccia di rete attiva con IPv4 valido (connetti cavo Ethernet o Wi-Fi)."
    elif wired:
        nic_status = "ok"
        w0 = wired[0]
        nic_msg = f"Interfaccia cablata attiva: {w0['name']} ({w0['ip']}). Pronta per BACnet, KNX e ARP."
    else:
        nic_status = "warning"
        wl0 = wireless[0]
        nic_msg = f"Rete Wi-Fi attiva: {wl0['name']} ({wl0['ip']}). Consigliata connessione cablata per scansioni bus/LAN."

    net_res = {
        "status": nic_status,
        "message": nic_msg,
        "total_active": len(nics),
        "interfaces": nics,
    }

    # 3. Test Privilegi OS & Driver
    priv_warnings = list(priv.warnings)
    if os_type == "windows":
        from scanners.ip_sniffer import npcap_installed
        has_npcap = npcap_installed()
        if not has_npcap:
            priv_warnings.append("Driver Npcap non installato: ARP Sniffer non disponibile.")

    if not priv_warnings:
        priv_status = "ok"
        priv_msg = "Privilegi di sistema e driver operativi al 100%."
    elif any("negato" in w.lower() or "mancante" in w.lower() or "richiede" in w.lower() for w in priv_warnings):
        priv_status = "warning"
        priv_msg = f"{len(priv_warnings)} avviso/i sui permessi (alcune funzioni avanzate disabilitate)."
    else:
        priv_status = "ok"
        priv_msg = "Privilegi di base OK."

    priv_res = {
        "status": priv_status,
        "message": priv_msg,
        "is_root_or_admin": priv.is_root_or_admin,
        "warnings": priv_warnings,
    }

    # Overall summary
    statuses = [serial_res["status"], net_res["status"], priv_res["status"]]
    if "error" in statuses:
        overall = "error"
    elif "warning" in statuses:
        overall = "warning"
    else:
        overall = "ok"

    return {
        "timestamp": time.time(),
        "overall": overall,
        "serial": serial_res,
        "network": net_res,
        "privileges": priv_res,
    }


def get_host_lan_ips() -> list[str]:
    """
    Ritorna la lista di indirizzi IPv4 locali non-loopback per consentire l'accesso da rete LAN.
    Esclude 127.x.x.x (loopback) e 169.254.x.x (link-local).
    """
    ips: set[str] = set()
    try:
        for nic in list_network_interfaces():
            ip = nic.get("ip")
            if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                ips.add(ip)
    except Exception:
        pass

    if not ips:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                    ips.add(ip)
            except Exception:
                pass
            finally:
                s.close()
        except Exception:
            pass

    if not ips:
        try:
            import socket
            host = socket.gethostname()
            for info in socket.getaddrinfo(host, None, socket.AF_INET):
                ip = info[4][0]
                if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                    ips.add(ip)
        except Exception:
            pass

    return sorted(ips)

