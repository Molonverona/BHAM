"""
BHAM – BMS & SCADA Tag Exporter
===============================
Esporta le liste punti e tag ingegnerizzati d'impianto (Modbus RTU/TCP, BACnet/IP)
nei formati standard compatibili con i principali supervisori di mercato:
1. Standard SCADA CSV (Ignition, Desigo CC, EcoStruxure, Movicon, WinCC)
2. Tridium Niagara 4 CSV (Modbus Async Network / Point Discovery CSV)
3. JSON Tag Dictionary (Node-RED, Edge Gateway, REST/MQTT bridges)
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

from data.maps_manager import maps_manager
from data.state import state


def _normalize_reg_type(rtype: str) -> tuple[str, str, str]:
    """
    Ritorna (niagara_reg_type, niagara_data_type, read_write)
    per Niagara 4 e SCADA.
    """
    r = (rtype or "holding").lower()
    if r in ("holding", "holding_register", "hr"):
        return "Holding", "Numeric", "RW"
    if r in ("input", "input_register", "ir"):
        return "Input", "Numeric", "RO"
    if r in ("coil", "coils", "c"):
        return "Coil", "Boolean", "RW"
    if r in ("discrete", "discrete_input", "di"):
        return "DiscreteInput", "Boolean", "RO"
    return "Holding", "Numeric", "RO"


def export_scada_tags(format_type: str = "standard_csv") -> tuple[str, str, str]:
    """
    Genera il file dei tag d'impianto.
    Restituisce: (content_string, media_type, filename)
    Formati supportati: 'standard_csv', 'niagara_csv', 'json'.
    """
    fmt = (format_type or "standard_csv").lower()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # 1. Raccoglie i punti Modbus
    points: list[dict[str, Any]] = []
    all_maps = maps_manager.get_all_maps()

    # Mappe registrate in MapsManager
    for slave_id, entries in all_maps.items():
        dev_label = f"Slave_{slave_id}"
        dev_desc = ""
        # Cerca nei dispositivi scoperti per arricchire il nome
        for k, dev in state.modbus_devices.items():
            if dev.slave_id == slave_id:
                if dev.product_name or dev.vendor_name:
                    dev_label = f"{dev.vendor_name or ''} {dev.product_name or ''} (ID {slave_id})".strip()
                dev_desc = dev.device_description or ""
                break

        for e in entries:
            tag_name = e.label or f"DEV{slave_id}_R{e.register}"
            niag_reg, niag_type, rw = _normalize_reg_type(e.register_type)
            points.append({
                "tag_name": tag_name,
                "protocol": "MODBUS",
                "device_id": str(slave_id),
                "device_label": dev_label,
                "address": e.register,
                "object_type": e.register_type.upper(),
                "data_type": niag_type,
                "scale": e.scale,
                "unit": e.unit,
                "access": rw,
                "description": e.description or dev_desc,
                "niagara_reg": niag_reg,
            })

    # Punti da dispositivi scoperti senza mappa formale ma con registri
    for k, dev in state.modbus_devices.items():
        if dev.slave_id in all_maps and all_maps[dev.slave_id]:
            continue
        dev_label = f"{dev.vendor_name or 'Modbus'} {dev.product_name or ''} (ID {dev.slave_id})".strip()
        for reg_addr, reg_val in dev.registers.items():
            try:
                addr_int = int(str(reg_addr).replace("0x", ""), 16 if "0x" in str(reg_addr) else 10)
            except ValueError:
                addr_int = 0
            reg_dict = reg_val if isinstance(reg_val, dict) else {}
            tag_name = reg_dict.get("label") or reg_dict.get("name") or f"DEV{dev.slave_id}_REG{addr_int}"
            reg_type = str(reg_dict.get("type") or reg_dict.get("register_type") or "holding").lower()
            niag_reg, niag_type, rw = _normalize_reg_type(reg_type)
            unit = str(reg_dict.get("unit") or "")
            scale = float(reg_dict.get("scale") or 1.0)
            desc = reg_dict.get("description") or f"Registro scansionato {addr_int}"

            points.append({
                "tag_name": tag_name,
                "protocol": "MODBUS",
                "device_id": str(dev.slave_id),
                "device_label": dev_label,
                "address": addr_int,
                "object_type": reg_type.upper(),
                "data_type": niag_type,
                "scale": scale,
                "unit": unit,
                "access": rw,
                "description": desc,
                "niagara_reg": niag_reg,
            })

    # 2. Raccoglie i punti BACnet
    for dev_id, bdev in state.bacnet_devices.items():
        dev_label = f"{bdev.vendor_name or 'BACnet'} {bdev.model_name or ''} ({dev_id})".strip()
        for obj in bdev.object_list:
            obj_id = str(obj.get("object-identifier") or obj.get("object_identifier") or "")
            obj_name = str(obj.get("object-name") or obj.get("object_name") or obj_id)
            obj_units = str(obj.get("units") or "")
            obj_type = "ANALOG_INPUT"
            rw = "RO"
            if "analog-output" in obj_id or "analogOutput" in obj_id:
                obj_type = "ANALOG_OUTPUT"
                rw = "RW"
            elif "binary-output" in obj_id or "binaryOutput" in obj_id:
                obj_type = "BINARY_OUTPUT"
                rw = "RW"
            elif "binary-input" in obj_id or "binaryInput" in obj_id:
                obj_type = "BINARY_INPUT"
            elif "analog-value" in obj_id or "analogValue" in obj_id:
                obj_type = "ANALOG_VALUE"
                rw = "RW"
            elif "binary-value" in obj_id or "binaryValue" in obj_id:
                obj_type = "BINARY_VALUE"
                rw = "RW"

            points.append({
                "tag_name": obj_name.replace(" ", "_"),
                "protocol": "BACNET",
                "device_id": str(dev_id),
                "device_label": dev_label,
                "address": obj_id,
                "object_type": obj_type,
                "data_type": "Boolean" if "BINARY" in obj_type else "Numeric",
                "scale": 1.0,
                "unit": obj_units,
                "access": rw,
                "description": f"BACnet object {obj_id}",
                "niagara_reg": obj_type,
            })

    # 3. Generazione formato richiesto
    if fmt == "niagara_csv":
        out = io.StringIO()
        writer = csv.writer(out, delimiter=",", lineterminator="\r\n")
        # Header standard per importazione punti Modbus Async in Niagara 4
        writer.writerow(["Name", "Address", "RegType", "Length", "DataType", "Scale", "Units", "ReadWrite", "Device"])
        for p in points:
            writer.writerow([
                p["tag_name"],
                p["address"],
                p["niagara_reg"],
                1,
                p["data_type"],
                p["scale"],
                p["unit"],
                p["access"],
                p["device_label"],
            ])
        return out.getvalue(), "text/csv; charset=utf-8", f"BHAM_Niagara_Tags_{timestamp}.csv"

    if fmt == "json":
        data = {
            "application": "BHAM (BACS Help Auto Mapper)",
            "version": "1.3.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_points": len(points),
            "points": points,
        }
        return json.dumps(data, indent=2, ensure_ascii=False), "application/json", f"BHAM_Tags_{timestamp}.json"

    # Default: Standard SCADA CSV
    out = io.StringIO()
    writer = csv.writer(out, delimiter=",", lineterminator="\r\n")
    writer.writerow([
        "Tag_Name",
        "Protocol",
        "Device_ID",
        "Device_Label",
        "Address",
        "Object_Type",
        "Data_Type",
        "Scale",
        "Unit",
        "Access_Mode",
        "Description",
    ])
    for p in points:
        writer.writerow([
            p["tag_name"],
            p["protocol"],
            p["device_id"],
            p["device_label"],
            p["address"],
            p["object_type"],
            p["data_type"],
            p["scale"],
            p["unit"],
            p["access"],
            p["description"],
        ])
    return out.getvalue(), "text/csv; charset=utf-8", f"BHAM_SCADA_Tags_{timestamp}.csv"
