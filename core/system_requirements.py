"""
BHAM – System Requirements & Cross-Platform Diagnostics
Comprehensive pre-flight and runtime environment validation for Windows and Linux:
- Python runtime & virtualenv integrity
- L2 raw packet capture drivers (Npcap on Windows, CAP_NET_RAW / libpcap on Linux)
- Serial RS485 communication readiness (COMx on Windows, dialout on Linux)
- Companion tools (Npcap installer, Wireshark/tshark)
- Automated companion downloading upon explicit user confirmation
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Optional

from core.logger import logger
from core.paths import get_data_dir

log = logger.getChild("sys_req")

_SYSTEM = platform.system()  # "Windows" | "Linux" | "Darwin"
NPCAP_DOWNLOAD_URL = "https://npcap.com/dist/npcap-1.80.exe"
NPCAP_FILENAME = "npcap-1.80.exe"


def is_windows() -> bool:
    return _SYSTEM == "Windows"


def is_linux() -> bool:
    return _SYSTEM == "Linux"


def is_in_venv() -> bool:
    """True se il processo è in esecuzione all'interno di un virtualenv Python."""
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def get_python_info() -> dict[str, Any]:
    """Ritorna informazioni dettagliate sull'interprete Python corrente."""
    ver = sys.version_info
    return {
        "version": f"{ver.major}.{ver.minor}.{ver.micro}",
        "major": ver.major,
        "minor": ver.minor,
        "executable": sys.executable,
        "is_venv": is_in_venv(),
        "is_supported": (ver.major == 3 and ver.minor in (12, 13)),
        "architecture": platform.machine(),
    }


def check_npcap_installed() -> bool:
    """
    Rileva se il driver Npcap (o WinPcap legacy) è presente nel sistema Windows.
    Su Linux/macOS ritorna sempre True (Npcap è una dipendenza specifica di Windows).
    """
    if not is_windows():
        return True

    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    candidates = [
        os.path.join(sysroot, "System32", "Npcap", "wpcap.dll"),
        os.path.join(sysroot, "System32", "wpcap.dll"),
        os.path.join(sysroot, "SysWOW64", "Npcap", "wpcap.dll"),
        os.path.join(sysroot, "SysWOW64", "wpcap.dll"),
    ]
    return any(os.path.isfile(c) for c in candidates)


def check_tshark_installed() -> bool:
    """True se Wireshark / TShark è disponibile per catture PCAP avanzate."""
    if shutil.which("tshark"):
        return True
    if is_windows():
        candidates = [
            r"C:\Program Files\Wireshark\tshark.exe",
            r"C:\Program Files (x86)\Wireshark\tshark.exe",
        ]
        return any(os.path.isfile(c) for c in candidates)
    return False


def get_downloads_dir() -> Path:
    """Cartella sicura dove scaricare installer e companion tools."""
    d = get_data_dir() / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def is_npcap_installer_cached() -> Optional[Path]:
    """Ritorna il path dell'installer Npcap se già scaricato in precedenza."""
    p = get_downloads_dir() / NPCAP_FILENAME
    if p.is_file() and p.stat().st_size > 100_000:
        return p
    return None


def download_npcap(dest_dir: Optional[Path] = None, timeout_s: float = 60.0) -> Path:
    """
    Scarica l'installer ufficiale di Npcap per Windows nella cartella specificata.
    Solleva un'eccezione in caso di errore di rete o timeout.
    """
    target_dir = dest_dir or get_downloads_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_path = target_dir / NPCAP_FILENAME

    log.info("Download Npcap in corso da %s verso %s ...", NPCAP_DOWNLOAD_URL, dest_path)

    # Headers standard per evitare blocchi anti-scraping
    req = urllib.request.Request(
        NPCAP_DOWNLOAD_URL,
        headers={"User-Agent": "BHAM-FieldStation/1.1.0 (Windows Installer Helper)"},
    )

    with urllib.request.urlopen(req, timeout=timeout_s) as response:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(response, f)

    if not dest_path.is_file() or dest_path.stat().st_size < 100_000:
        if dest_path.exists():
            dest_path.unlink()
        raise RuntimeError("Il file scaricato di Npcap è incompleto o non valido.")

    log.info("Download Npcap completato con successo: %s (%d byte)", dest_path, dest_path.stat().st_size)
    return dest_path


def get_system_diagnostics() -> dict[str, Any]:
    """
    Genera un quadro diagnostico unificato dello stato del sistema, dei driver e dei permessi.
    """
    from core.hw_discovery import list_network_interfaces, list_serial_ports
    from core.priv_check import check_privileges

    priv = check_privileges()
    py_info = get_python_info()
    npcap_ok = check_npcap_installed()
    tshark_ok = check_tshark_installed()

    try:
        serials = list_serial_ports()
    except Exception:
        serials = []

    try:
        nics = list_network_interfaces()
    except Exception:
        nics = []

    missing: list[str] = []
    recommendations: list[str] = []

    if not py_info["is_supported"]:
        missing.append(f"Python {py_info['version']} non ufficialmente supportato (richiesto 3.12 o 3.13)")
        recommendations.append("Installa Python 3.12 ufficiale per garantire stabilità ai driver BACS.")

    if is_windows():
        if not npcap_ok:
            missing.append("Driver Npcap mancante su Windows (wpcap.dll)")
            recommendations.append("Installa Npcap per abilitare la cattura ARP passiva e lo sniffer di rete.")
        if not priv.is_root_or_admin:
            recommendations.append("Esegui BHAM come Amministratore se desideri usare le raw socket su Windows.")
    elif is_linux():
        if not priv.has_cap_net_raw and not priv.is_root_or_admin:
            missing.append("Permesso di rete CAP_NET_RAW mancante su Linux")
            recommendations.append("Esegui: sudo setcap cap_net_raw+eip " + sys.executable)
        if not priv.has_dialout and not priv.is_root_or_admin:
            missing.append("Utente non appartenente al gruppo 'dialout'")
            recommendations.append("Esegui: sudo usermod -aG dialout $USER (e riavvia la sessione)")

    has_packet_capture = (npcap_ok and priv.is_root_or_admin) if is_windows() else (priv.has_cap_net_raw or priv.is_root_or_admin)
    has_serial_access = True if is_windows() else (priv.has_dialout or priv.is_root_or_admin)

    return {
        "os": _SYSTEM.lower(),
        "os_name": _SYSTEM,
        "os_release": platform.release(),
        "os_version": platform.version(),
        "arch": platform.machine(),
        "python": py_info,
        "is_admin_or_root": priv.is_root_or_admin,
        "has_packet_capture": has_packet_capture,
        "has_npcap": npcap_ok,
        "npcap_cached": is_npcap_installer_cached() is not None,
        "has_serial_access": has_serial_access,
        "serial_ports_count": len(serials),
        "network_interfaces_count": len(nics),
        "tshark_available": tshark_ok,
        "missing_requirements": missing,
        "recommendations": recommendations,
        "is_healthy": len(missing) == 0,
    }
