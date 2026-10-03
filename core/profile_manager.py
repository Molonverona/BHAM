"""
BHAM – Modbus Device Profiles Manager ("Libreria Profili Dispositivi")
=====================================================================
Manages offline device profiles for industrial multimeters, heat/flow meters,
actuators, and HVAC controllers (ABB, Gavazzi, IME, Schneider, Siemens, Belimo,
Isoil, Diehl, Emerson, iSMA CONTROLLI, Riello, Carel).
Supports:
  - Built-in factory library (read-only bundled assets)
  - Custom profiles (stored in user data directory)
  - Import/Export of profile JSON definitions
  - "Apply to Slave": maps registers and descriptions directly onto a discovered slave
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from core.logger import logger
from core.paths import get_builtin_profiles_dir, get_profiles_dir
from data.state import state

log = logger.getChild("profile_manager")


def _slugify(text: str) -> str:
    """Generate safe alphanumeric ID with underscores."""
    s = re.sub(r"[^\w\s-]", "", text.strip().lower())
    return re.sub(r"[-\s]+", "_", s)


class ProfileManager:
    """
    Central repository for Modbus profiles (Built-in factory + User Custom).
    """

    def __init__(self) -> None:
        self._builtin_dir = get_builtin_profiles_dir()
        self._custom_dir = get_profiles_dir()
        self._profiles_cache: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        """Reload all profiles from disk."""
        self._profiles_cache.clear()

        # 1. Load Builtin profiles
        if self._builtin_dir.exists():
            for p in self._builtin_dir.glob("*.json"):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    pid = data.get("id") or p.stem
                    data["id"] = pid
                    data["is_builtin"] = True
                    self._profiles_cache[pid] = data
                except Exception as exc:
                    log.error("Errore caricamento profilo builtin %s: %s", p.name, exc)

        # 2. Load Custom profiles (can override or supplement)
        if self._custom_dir.exists():
            for p in self._custom_dir.glob("*.json"):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    pid = data.get("id") or p.stem
                    data["id"] = pid
                    data["is_builtin"] = False
                    self._profiles_cache[pid] = data
                except Exception as exc:
                    log.error("Errore caricamento profilo custom %s: %s", p.name, exc)

        log.info("Libreria profili caricata: %d profili disponibili", len(self._profiles_cache))

    def list_profiles(self, category: Optional[str] = None) -> list[dict[str, Any]]:
        """List all profiles, optionally filtered by category (multimeter, energy_heat, actuator_hvac, custom)."""
        res = []
        cat_filter = str(category).lower() if (category and isinstance(category, str)) else None
        for p in self._profiles_cache.values():
            if cat_filter and cat_filter != "all":
                if p.get("category", "").lower() != cat_filter:
                    continue
            res.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "category": p.get("category", "custom"),
                "manufacturer": p.get("manufacturer", ""),
                "model": p.get("model", ""),
                "description": p.get("description", ""),
                "is_builtin": p.get("is_builtin", False),
                "point_count": len(p.get("points", [])),
                "default_baudrate": p.get("default_baudrate", 9600),
                "default_parity": p.get("default_parity", "N"),
            })
        return sorted(res, key=lambda x: (x.get("category", ""), x.get("manufacturer", ""), x.get("name", "")))

    def get_profile(self, profile_id: str) -> Optional[dict[str, Any]]:
        """Return full profile by ID."""
        return self._profiles_cache.get(profile_id)

    def save_custom_profile(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate and persist a custom profile into user data directory."""
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("Il nome del profilo è obbligatorio.")

        pid = data.get("id") or _slugify(name)
        # Prevent overwriting builtin profiles with custom unless suffixed
        if pid in self._profiles_cache and self._profiles_cache[pid].get("is_builtin"):
            pid = f"{pid}_custom"

        profile_data = {
            "id": pid,
            "name": name,
            "category": data.get("category") or "custom",
            "manufacturer": (data.get("manufacturer") or "").strip(),
            "model": (data.get("model") or "").strip(),
            "description": (data.get("description") or "").strip(),
            "default_baudrate": int(data.get("default_baudrate") or 9600),
            "default_parity": (data.get("default_parity") or "N").upper(),
            "default_stopbits": int(data.get("default_stopbits") or 1),
            "points": data.get("points") or [],
            "is_builtin": False,
        }

        # Normalize points
        normalized_points = []
        for pt in profile_data["points"]:
            normalized_points.append({
                "address": int(pt.get("address", 0)),
                "name": str(pt.get("name", "")).strip() or f"Register_{pt.get('address')}",
                "type": str(pt.get("type", "holding")).lower(),
                "format": str(pt.get("format", "uint16")).lower(),
                "unit": str(pt.get("unit", "")).strip(),
                "scale": float(pt.get("scale", 1.0)),
                "access": str(pt.get("access", "ro")).lower(),
                "description": str(pt.get("description", "")).strip(),
            })
        profile_data["points"] = normalized_points

        target_file = self._custom_dir / f"{pid}.json"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(json.dumps(profile_data, indent=2, ensure_ascii=False), encoding="utf-8")

        self._profiles_cache[pid] = profile_data
        log.info("Profilo custom salvato: %s (%s)", name, target_file)
        return profile_data

    def delete_custom_profile(self, profile_id: str) -> bool:
        """Delete custom profile from disk (Built-in profiles cannot be deleted)."""
        p = self._profiles_cache.get(profile_id)
        if not p:
            raise FileNotFoundError(f"Profilo '{profile_id}' non trovato.")
        if p.get("is_builtin"):
            raise ValueError(f"Impossibile eliminare un profilo factory di fabbrica ({profile_id}).")

        target_file = self._custom_dir / f"{profile_id}.json"
        if target_file.exists():
            target_file.unlink()

        del self._profiles_cache[profile_id]
        log.info("Profilo custom eliminato: %s", profile_id)
        return True

    def apply_profile_to_slave(self, slave_id: int, profile_id: str) -> dict[str, Any]:
        """
        Applies a profile to a Modbus slave in active state.
        Injects labels, units, and register mapping into state and MapsManager.
        """
        profile = self.get_profile(profile_id)
        if not profile:
            raise ValueError(f"Profilo '{profile_id}' non trovato nella libreria.")

        dev = state.modbus_devices.get(slave_id)
        if not dev:
            # Create placeholder if slave not yet discovered
            from data.models import ModbusDevice
            dev = ModbusDevice(slave_id=slave_id, state="active")
            state.modbus_devices[slave_id] = dev

        # Enrich device metadata
        dev.vendor_name = profile.get("manufacturer") or dev.vendor_name
        dev.product_name = profile.get("model") or profile.get("name") or dev.product_name
        dev.device_description = profile.get("description") or dev.device_description

        # Integrate points into MapsManager
        from data.maps_manager import maps_manager
        applied_points = []
        for pt in profile.get("points", []):
            pt_dict = {
                "slave_id": slave_id,
                "address": pt.get("address"),
                "name": pt.get("name"),
                "type": pt.get("type", "holding"),
                "format": pt.get("format", "uint16"),
                "unit": pt.get("unit", ""),
                "scale": pt.get("scale", 1.0),
                "access": pt.get("access", "ro"),
                "description": pt.get("description", ""),
            }
            applied_points.append(pt_dict)

            # Update dev.registers if present
            addr = pt.get("address")
            if addr is not None and addr in dev.registers:
                dev.registers[addr]["name"] = pt.get("name")
                dev.registers[addr]["unit"] = pt.get("unit")
                dev.registers[addr]["description"] = pt.get("description")

        maps_manager.import_from_json(applied_points)
        log.info("Applicato profilo '%s' su slave #%d (%d registri mappati)", profile.get("name"), slave_id, len(applied_points))

        return {
            "success": True,
            "slave_id": slave_id,
            "profile_id": profile_id,
            "profile_name": profile.get("name"),
            "manufacturer": profile.get("manufacturer"),
            "mapped_points_count": len(applied_points),
            "points": applied_points,
        }


# Global singleton instance
profile_manager = ProfileManager()
