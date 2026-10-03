"""
BHAM – Centralized Path Management
Resolves project root, bundled assets, user data directories, and portable vs installed mode.
Works consistently in development, venv, and PyInstaller frozen single-binary/folder bundles.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """Return True if running as a compiled PyInstaller executable."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_bundle_dir() -> Path:
    """
    Return the base directory for read-only bundled assets (frontend, builtin profiles).
    In frozen mode, this is sys._MEIPASS. In source mode, this is the project root.
    """
    if is_frozen():
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).parent.parent.resolve()


def get_executable_dir() -> Path:
    """
    Return the directory where the current executable or launcher script resides.
    Used to check for portable.flag and store local data in portable mode.
    """
    if is_frozen():
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.parent.resolve()


def is_portable() -> bool:
    """
    Return True if running in portable mode.
    Portable mode is activated if:
      1. A 'portable.flag' file exists next to the executable.
      2. A 'data' or 'sessions' directory exists next to the executable.
      3. The BHAM_PORTABLE environment variable is set to '1' or 'true'.
    """
    if os.environ.get("BHAM_PORTABLE", "").lower() in ("1", "true", "yes"):
        return True
    exe_dir = get_executable_dir()
    if (exe_dir / "portable.flag").exists():
        return True
    if (exe_dir / "data").is_dir() and not is_frozen():
        return True
    return False


def get_data_dir() -> Path:
    """
    Return the writable directory for dynamic user data (sessions, custom profiles, audit logs).
    In portable mode: returns <executable_dir>/data (or root/sessions).
    In installed mode:
      - Windows: %LOCALAPPDATA%/BHAM
      - Linux: ~/.local/share/bham or XDG_DATA_HOME/bham
    """
    if is_portable():
        data_dir = get_executable_dir() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            d = Path(base) / "BHAM"
            d.mkdir(parents=True, exist_ok=True)
            return d

    # Linux / macOS standard
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        d = Path(xdg_data) / "bham"
    else:
        d = Path.home() / ".local" / "share" / "bham"

    # Fallback to local project root if home is not writable
    try:
        d.mkdir(parents=True, exist_ok=True)
        return d
    except (OSError, PermissionError):
        fallback = get_executable_dir() / "data"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def get_sessions_dir() -> Path:
    """Return the directory where scan sessions and historical snapshots are saved."""
    exe_dir = get_executable_dir()
    if (exe_dir / "sessions").is_dir() or is_portable():
        d = exe_dir / "sessions"
        d.mkdir(parents=True, exist_ok=True)
        return d
    d = get_data_dir() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_profiles_dir() -> Path:
    """Return the user-writable directory for custom/imported Modbus device profiles."""
    d = get_data_dir() / "profiles" / "custom"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_builtin_profiles_dir() -> Path:
    """Return the directory containing bundled builtin device profiles."""
    d = get_bundle_dir() / "profiles" / "builtin"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_frontend_dir() -> Path:
    """Return the directory serving the frontend static files."""
    return get_bundle_dir() / "frontend"


def get_audit_journal_path() -> Path:
    """Return the canonical path for the append-only crash-proof audit journal."""
    return get_sessions_dir() / "audit_journal.jsonl"
