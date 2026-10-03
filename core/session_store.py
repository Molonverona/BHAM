"""
BHAM – Session Store
Persistenza opzionale delle sessioni su file JSON nominati in sessions/.
Non viene mai auto-caricato all'avvio: è un archivio consultabile.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from core.paths import get_sessions_dir

log = logging.getLogger("bham").getChild("session_store")


def _ensure_dir() -> Path:
    d = get_sessions_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_session(
    name: str,
    config: dict[str, Any],
    state_snapshot: dict[str, Any],
    log_path: Optional[Path] = None,
) -> Path:
    """
    Salva un profilo sessione su disco.

    Args:
        name:           Nome libero del tecnico (es. "Cliente Rossi – Impianto 3")
        config:         SessionConfig serializzato
        state_snapshot: Output di AppState.snapshot()
        log_path:       Path del log di sessione da copiare (opzionale)

    Returns:
        Path del file JSON salvato.
    """
    d = _ensure_dir()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in name)
    safe_name = safe_name.strip().replace(" ", "_")[:60]
    json_path = d / f"{ts}_{safe_name}.json"

    copied_log: Optional[str] = None
    if log_path and Path(log_path).exists():
        dest_log = d / f"{ts}_{safe_name}.log"
        shutil.copy2(log_path, dest_log)
        copied_log = str(dest_log)
        log.debug("Log copiato in %s", dest_log)

    payload: dict[str, Any] = {
        "name":     name,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "config":   config,
        "results":  state_snapshot,
        "log_path": copied_log,
    }

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str, ensure_ascii=False)

    log.info("Sessione salvata: %s", json_path)
    return json_path


def list_sessions() -> list[dict[str, Any]]:
    """
    Elenca sessioni salvate (ordine cronologico inverso).
    NON carica i risultati completi per efficienza.
    """
    d = _ensure_dir()
    sessions: list[dict] = []

    for p in sorted(d.glob("*.json"), reverse=True):
        try:
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
            results = data.get("results", {})
            sessions.append({
                "filename":      p.name,
                "name":          data.get("name", p.stem),
                "saved_at":      data.get("saved_at", ""),
                "has_log":       bool(data.get("log_path")),
                "size_bytes":    p.stat().st_size,
                "device_counts": {
                    "modbus":   len(results.get("modbus_devices", [])),
                    "bacnet":   len(results.get("bacnet_devices", [])),
                    "knx":      len(results.get("knx_devices", [])),
                    "ip_hosts": len(results.get("ip_hosts", [])),
                },
            })
        except Exception as exc:
            log.warning("Impossibile leggere sessione %s: %s", p.name, exc)

    return sessions


def load_session(filename: str) -> dict[str, Any]:
    """
    Carica il JSON completo di una sessione (sola lettura).

    Raises:
        FileNotFoundError: file non trovato.
        ValueError: path traversal rilevato.
    """
    safe = Path(filename).name
    if safe != filename:
        raise ValueError(f"Filename non sicuro: {filename!r}")
    p = _ensure_dir() / safe
    if not p.exists():
        raise FileNotFoundError(f"Sessione non trovata: {filename}")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def delete_session(filename: str) -> None:
    """Elimina JSON + eventuale log di una sessione."""
    safe = Path(filename).name
    if safe != filename:
        raise ValueError(f"Filename non sicuro: {filename!r}")
    p = _ensure_dir() / safe
    if not p.exists():
        raise FileNotFoundError(f"Sessione non trovata: {filename}")
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        lp = data.get("log_path")
        if lp and Path(lp).exists():
            Path(lp).unlink()
    except Exception:
        pass
    p.unlink()
    log.info("Sessione eliminata: %s", filename)
