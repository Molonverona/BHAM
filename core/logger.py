"""
BHAM – Structured Logger
Provides a single shared logger with coloured console output and optional
file rotation, broadcast-ready for WebSocket streaming.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable

_HANDLERS: list[Callable[[str], None]] = []   # WebSocket broadcast hooks


class _WebSocketHandler(logging.Handler):
    """Emits log records to all registered async broadcast hooks."""

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        for hook in _HANDLERS:
            try:
                hook(msg)
            except Exception:
                pass


def register_ws_hook(hook: Callable[[str], None]) -> None:
    """Register a broadcast hook called on every log record."""
    _HANDLERS.append(hook)


def _build_logger(name: str = "bham") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Console
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(logging.DEBUG)
    logger.addHandler(sh)

    # Rotating file (5 MB × 3)
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    fh = RotatingFileHandler(
        log_dir / "bham.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    # WebSocket stream
    wsh = _WebSocketHandler()
    wsh.setFormatter(fmt)
    wsh.setLevel(logging.INFO)
    logger.addHandler(wsh)

    return logger


logger = _build_logger()

# ── Session log handler ───────────────────────────────────────────────────────

_session_handler: logging.FileHandler | None = None


def start_session_log(session_name: str) -> Path:
    """
    Apre un FileHandler aggiuntivo su sessions/<ts>_<name>.log.
    Tutti i record del logger 'bham' vengono scritti anche in quel file.

    Args:
        session_name: Nome libero della sessione (verrà sanitizzato).

    Returns:
        Path del file di log aperto.
    """
    global _session_handler

    from pathlib import Path  # local import per evitare circolare a livello modulo
    import time

    stop_session_log()  # chiudi eventuale handler precedente

    sessions_dir = Path("sessions")
    sessions_dir.mkdir(parents=True, exist_ok=True)

    ts = time.strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in session_name)
    safe = safe.strip().replace(" ", "_")[:60]
    log_path = sessions_dir / f"{ts}_{safe}.log"

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    _session_handler = logging.FileHandler(log_path, encoding="utf-8")
    _session_handler.setFormatter(fmt)
    _session_handler.setLevel(logging.DEBUG)
    logger.addHandler(_session_handler)
    logger.info("Log di sessione avviato: %s", log_path)
    return log_path


def stop_session_log() -> None:
    """Rimuove e chiude il FileHandler di sessione corrente (se attivo)."""
    global _session_handler
    if _session_handler is not None:
        logger.info("Log di sessione chiuso.")
        logger.removeHandler(_session_handler)
        _session_handler.close()
        _session_handler = None


def current_session_log_path() -> Path | None:
    """Ritorna il path del log di sessione corrente, o None se non attivo."""
    if _session_handler is not None:
        return Path(_session_handler.baseFilename)
    return None
