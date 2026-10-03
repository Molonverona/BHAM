"""
BHAM – Privilege / Permission Checker
Centralised runtime checks for OS-level permissions required by BHAM.

Usage (called at app startup):
    from core.priv_check import check_privileges
    check_privileges()          # logs warnings – never raises
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from typing import NamedTuple

from core.logger import logger

log = logger.getChild("priv_check")

_SYSTEM = platform.system()  # "Linux" | "Windows" | "Darwin"


# ── Result container ──────────────────────────────────────────────────────────

class PrivReport(NamedTuple):
    is_root_or_admin: bool
    has_cap_net_raw: bool   # Linux only (always True on Windows / if root)
    has_dialout: bool       # Linux only (always True on Windows)
    warnings: list[str]


# ── Linux helpers ─────────────────────────────────────────────────────────────

def _linux_has_cap_net_raw() -> bool:
    """
    True when the current process has CAP_NET_RAW.
    Works even when running without root if setcap was applied.
    """
    try:
        # /proc/self/status exposes CapPrm (permitted) bitmask
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("CapPrm:"):
                    cap_prm = int(line.split(":")[1].strip(), 16)
                    # CAP_NET_RAW = bit 13
                    return bool(cap_prm & (1 << 13))
    except Exception:
        pass
    # Fallback: try to open a raw socket (cheapest real test)
    try:
        import socket
        s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, 0)
        s.close()
        return True
    except (PermissionError, OSError, AttributeError):
        return False


def _linux_has_dialout() -> bool:
    """
    True quando l'utente appartiene a 'dialout'/'uucp' oppure ha accesso diretto in lettura/scrittura
    alle porte seriali connesse (/dev/ttyUSB*, /dev/ttyACM*).
    """
    try:
        import grp
        gids = os.getgroups()
        for grp_name in ("dialout", "uucp"):
            try:
                if grp.getgrnam(grp_name).gr_gid in gids:
                    return True
            except KeyError:
                pass
    except Exception:
        pass

    # Verifica se una qualsiasi porta seriale connessa è già accessibile con permessi rw (ACL/udev/nogroup)
    import glob
    for dev in glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"):
        try:
            if os.access(dev, os.R_OK | os.W_OK):
                return True
        except Exception:
            pass

    return False


def _linux_report() -> PrivReport:
    is_root = os.geteuid() == 0
    cap_net_raw = is_root or _linux_has_cap_net_raw()
    dialout = is_root or _linux_has_dialout()
    warnings: list[str] = []

    if not cap_net_raw:
        warnings.append(
            "⚠️  ARP Sniffer non disponibile: cap_net_raw mancante.\n"
            "   Per abilitarlo (una-tantum, senza sudo permanente):\n"
            f"     sudo setcap cap_net_raw+eip {sys.executable}\n"
            "   oppure esegui BHAM con:  sudo python3 main.py"
        )

    if not dialout:
        warnings.append(
            "⚠️  Serial RS485 non disponibile: utente non nel gruppo 'dialout'.\n"
            "   Aggiungi il tuo utente (richiede logout/login):\n"
            f"     sudo usermod -aG dialout {os.environ.get('USER', '$USER')}\n"
            "   Poi esegui di nuovo BHAM."
        )

    return PrivReport(is_root, cap_net_raw, dialout, warnings)


# ── Windows helpers ───────────────────────────────────────────────────────────

def _windows_is_admin() -> bool:
    """True when the current process has Administrator token."""
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _windows_report() -> PrivReport:
    is_admin = _windows_is_admin()
    warnings: list[str] = []

    if not is_admin:
        warnings.append(
            "⚠️  ARP Sniffer richiede privilegi Administrator.\n"
            "   Riesegui BHAM come Amministratore:\n"
            "     Tasto destro su bham.exe → 'Esegui come amministratore'\n"
            "   Le porte COM seriali funzionano senza elevazione su Windows.\n"
            "   L'ARP sniffer verrà disabilitato automaticamente."
        )

    return PrivReport(is_admin, is_admin, True, warnings)


# ── Public API ────────────────────────────────────────────────────────────────

_cached_report: PrivReport | None = None


def check_privileges() -> PrivReport:
    """
    Run the privilege check for the current OS and cache the result.
    Logs all warnings at WARNING level.  Never raises.
    """
    global _cached_report
    if _cached_report is not None:
        return _cached_report

    try:
        if _SYSTEM == "Linux":
            report = _linux_report()
        elif _SYSTEM == "Windows":
            report = _windows_report()
        else:
            # macOS / other: minimal checks
            is_root = os.geteuid() == 0
            report = PrivReport(is_root, is_root, is_root, [])

        for warn in report.warnings:
            log.warning("%s", warn)

        if not report.warnings:
            log.info("✅  Controllo permessi OK (root=%s)", report.is_root_or_admin)

        _cached_report = report
        return report
    except Exception as exc:
        log.error("priv_check failed: %s", exc)
        fallback = PrivReport(False, False, False, [])
        _cached_report = fallback
        return fallback


def has_cap_net_raw() -> bool:
    """Convenience shortcut."""
    return check_privileges().has_cap_net_raw


def has_dialout() -> bool:
    """Convenience shortcut."""
    return check_privileges().has_dialout


def is_admin() -> bool:
    """Convenience shortcut."""
    return check_privileges().is_root_or_admin
