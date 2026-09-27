"""
BHAM – BACS Help Maps Manager
Handles point maps (JSON <-> in-memory state), register definitions,
and import/export operations compatible with BACS Help / Modbus profiles.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from core.logger import logger


class RegisterType(str, Enum):
    HOLDING = "holding"
    INPUT = "input"
    COIL = "coil"
    DISCRETE = "discrete"


@dataclass
class MapEntry:
    """Singola definizione di registro / punto Modbus."""
    slave_id: int
    register: int
    register_type: str = "holding"  # holding | input | coil | discrete
    label: str = ""
    unit: str = ""
    scale: float = 1.0
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MapEntry:
        # Normalizzazione chiavi comuni (address/register, type/register_type)
        reg = data.get("register", data.get("address", 0))
        reg_type = data.get("register_type", data.get("type", "holding")).lower()
        if reg_type in ("holding_register", "hr"):
            reg_type = "holding"
        elif reg_type in ("input_register", "ir"):
            reg_type = "input"
        elif reg_type in ("coils", "c"):
            reg_type = "coil"
        elif reg_type in ("discrete_input", "di"):
            reg_type = "discrete"

        return cls(
            slave_id=int(data.get("slave_id", 1)),
            register=int(reg),
            register_type=reg_type,
            label=str(data.get("label", data.get("name", ""))),
            unit=str(data.get("unit", "")),
            scale=float(data.get("scale", 1.0)),
            description=str(data.get("description", "")),
        )


class MapsManager:
    """Gestione in-memory delle mappe punti BACS Help con persistenza JSON."""

    def __init__(self) -> None:
        # Chiave: slave_id (int) -> Lista di MapEntry
        self._maps: dict[int, list[MapEntry]] = {}

    def clear(self) -> None:
        """Svuota tutte le mappe in memoria."""
        self._maps.clear()
        logger.info("MapsManager: tutte le mappe rimosse dalla memoria")

    def get_map(self, slave_id: int) -> list[MapEntry]:
        """Ritorna i punti mappati per un determinato slave ID."""
        return list(self._maps.get(slave_id, []))

    def get_all_maps(self) -> dict[int, list[MapEntry]]:
        """Ritorna l'intero dizionario delle mappe."""
        return {sid: list(entries) for sid, entries in self._maps.items()}

    def set_map(self, slave_id: int, entries: list[MapEntry]) -> None:
        """Imposta o sostituisce la mappa per un dato slave ID."""
        self._maps[slave_id] = list(entries)
        logger.info("MapsManager: slave_id=%d aggiornato con %d punti", slave_id, len(entries))

    def import_from_json(self, raw_data: Any) -> int:
        """
        Valida e importa definizioni punti da struttura dati JSON.
        Supporta diversi formati comuni BACS Help:
          1. Dict con chiave 'devices': [{"slave_id": 1, "points": [...]}, ...]
          2. Dict con chiave 'points': [{"slave_id": 1, "register": 100, ...}, ...]
          3. Dict mappato per slave ID: {"1": [...], "2": [...]}
          4. Lista diretta di punti: [{"slave_id": 1, "register": 100, ...}, ...]
        Ritorna il conteggio totale dei punti importati.
        """
        imported_count = 0
        extracted_entries: list[MapEntry] = []

        if isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, dict):
                    extracted_entries.append(MapEntry.from_dict(item))
        elif isinstance(raw_data, dict):
            if "devices" in raw_data and isinstance(raw_data["devices"], list):
                for dev in raw_data["devices"]:
                    sid = dev.get("slave_id", 1)
                    points = dev.get("points", [])
                    for pt in points:
                        if isinstance(pt, dict):
                            pt_copy = dict(pt)
                            pt_copy.setdefault("slave_id", sid)
                            extracted_entries.append(MapEntry.from_dict(pt_copy))
            elif "points" in raw_data and isinstance(raw_data["points"], list):
                for pt in raw_data["points"]:
                    if isinstance(pt, dict):
                        extracted_entries.append(MapEntry.from_dict(pt))
            else:
                # Controlla se le chiavi sono slave_id numerici
                for k, v in raw_data.items():
                    if k.isdigit() and isinstance(v, list):
                        sid = int(k)
                        for pt in v:
                            if isinstance(pt, dict):
                                pt_copy = dict(pt)
                                pt_copy.setdefault("slave_id", sid)
                                extracted_entries.append(MapEntry.from_dict(pt_copy))

        if not extracted_entries:
            logger.warning("MapsManager: nessun punto valido trovato nell'input JSON")
            return 0

        # Raggruppa e aggiorna per slave_id (upsert)
        for entry in extracted_entries:
            sid = entry.slave_id
            if sid not in self._maps:
                self._maps[sid] = []

            # Aggiorna se esiste già lo stesso (register, register_type)
            replaced = False
            for idx, existing in enumerate(self._maps[sid]):
                if existing.register == entry.register and existing.register_type == entry.register_type:
                    self._maps[sid][idx] = entry
                    replaced = True
                    break
            if not replaced:
                self._maps[sid].append(entry)

            imported_count += 1

        # Ordina per registro
        for sid in self._maps:
            self._maps[sid].sort(key=lambda x: (x.register_type, x.register))

        logger.info("MapsManager: importati %d punti su %d slave", imported_count, len(self._maps))
        return imported_count

    def export_to_json(self) -> dict[str, Any]:
        """Serializza lo stato in-memory in formato JSON BACS Help compatibile."""
        total_points = sum(len(pts) for pts in self._maps.values())
        devices_list = []
        for sid, entries in sorted(self._maps.items()):
            devices_list.append({
                "slave_id": sid,
                "point_count": len(entries),
                "points": [e.to_dict() for e in entries],
            })

        return {
            "format": "BACS_HELP_MAP",
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_points": total_points,
            "devices": devices_list,
        }


# ── Global Singleton ─────────────────────────────────────────────────────────
maps_manager = MapsManager()


# ── Backward compatibility helpers ───────────────────────────────────────────

def load_map(filepath: str) -> dict:
    """Load a BACS Help JSON map file and load it into maps_manager."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Map file not found: {filepath}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    maps_manager.import_from_json(data)
    logger.info("Loaded map from %s", filepath)
    return data


def save_map(data: dict, filepath: str) -> None:
    """Persist dictionary as a BACS Help-compatible JSON map."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info("Saved map to %s", filepath)
