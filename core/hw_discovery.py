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
