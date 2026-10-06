"""
BHAM – Field Tools & Override Engine ("Banco Prova & Override")
===============================================================
Industrial operational tools for commissioning engineers:
1. Modbus Quick Commander:
   - Read FC01 (Coils), FC02 (Discrete Inputs), FC03 (Holding Registers), FC04 (Input Registers)
   - Force/Write FC05 (Single Coil), FC06 (Single Holding Register),
     FC15 (Multiple Coils), FC16 (Multiple Holding Registers)
   - Automatic decoding/encoding: Dec, Hex, Int16 (signed), UInt16, Float32 (Big-Endian & Word-Swapped)
2. BACnet Point Commander:
   - Override presentValue on output and value objects (analogOutput, binaryOutput, multiState, etc.)
   - Full Priority Array compliance (default Priority 8: Manual Operator)
   - Relinquish capability (writes NULL to release manual operator override)
   - Integrated with Virtual Plant Simulator for testing in Demo Mode
"""

from __future__ import annotations

import asyncio
import struct
import time
from typing import Any, Optional

from core.audit_journal import audit_journal
from core.logger import logger
from core.safe_mode import safe_mode
from core.simulator import simulator

log = logger.getChild("field_tools")


# ── Modbus Conversions & Decoders ─────────────────────────────────────────────

def decode_modbus_value(registers: list[int]) -> dict[str, Any]:
    """
    Decodes a list of 16-bit registers into multiple technical representations:
    Dec, Hex, Int16, UInt16, Float32 (Big-Endian and Word-Swapped CDAB).
    """
    if not registers:
        return {}

    first = registers[0] & 0xFFFF
    int16_val = first if first < 32768 else first - 65536
    result: dict[str, Any] = {
        "raw_dec": first,
        "raw_hex": f"0x{first:04X}",
        "uint16": first,
        "int16": int16_val,
        "float32_be": None,
        "float32_le": None,
    }

    if len(registers) >= 2:
        r0 = registers[0] & 0xFFFF
        r1 = registers[1] & 0xFFFF
        try:
            # Big-Endian (ABCD)
            raw_bytes_be = struct.pack(">HH", r0, r1)
            result["float32_be"] = round(struct.unpack(">f", raw_bytes_be)[0], 4)
        except Exception:
            pass

        try:
            # Word-Swapped (CDAB)
            raw_bytes_le = struct.pack(">HH", r1, r0)
            result["float32_le"] = round(struct.unpack(">f", raw_bytes_le)[0], 4)
        except Exception:
            pass

    return result


def encode_modbus_value(val: Any, data_type: str = "uint16") -> list[int]:
    """
    Encodes a user value (int, float, bool) into a list of 16-bit register values.
    Supported types: 'uint16', 'int16', 'float32', 'float32_swapped', 'bool'
    """
    data_type = (data_type or "uint16").lower()

    if data_type in ("bool", "coil"):
        return [1 if bool(val) else 0]

    if data_type == "int16":
        ival = int(val)
        return [ival & 0xFFFF]

    if data_type in ("float", "float32", "float32_be"):
        fval = float(val)
        b = struct.pack(">f", fval)
        r0, r1 = struct.unpack(">HH", b)
        return [r0, r1]

    if data_type in ("float32_swapped", "float32_le", "float_cdab"):
        fval = float(val)
        b = struct.pack(">f", fval)
        r0, r1 = struct.unpack(">HH", b)
        return [r1, r0]

    # Default uint16
    return [int(val) & 0xFFFF]


# ── Modbus Quick Commander Execution ──────────────────────────────────────────

async def modbus_quick_read(
    protocol: str = "rtu",
    port: Optional[str] = None,
    baudrate: int = 9600,
    parity: str = "N",
    stopbits: int = 1,
    ip: Optional[str] = None,
    tcp_port: int = 502,
    slave_id: int = 1,
    function_code: int = 3,
    address: int = 0,
    count: int = 1,
    timeout: float = 0.8,
) -> dict[str, Any]:
    """
    Reads registers or coils from a Modbus device (physical or simulated).
    FC 1: Read Coils
    FC 2: Read Discrete Inputs
    FC 3: Read Holding Registers
    FC 4: Read Input Registers
    """
    t0 = time.monotonic()
    count = max(1, min(count, 125))

    # Se il simulatore è attivo e l'indirizzo/porta corrisponde a un device virtuale
    if simulator.is_active:
        values: list[Any] = []
        if function_code in (1, 2):
            for i in range(count):
                values.append(simulator.read_modbus_coil(slave_id, address + i))
        else:
            for i in range(count):
                values.append(simulator.read_modbus_register(slave_id, address + i))

        decoding = decode_modbus_value(values) if function_code in (3, 4) else {}
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        regs = values if function_code in (3, 4) else []
        coils = values if function_code in (1, 2) else []
        return {
            "success": True,
            "status": "ok",
            "slave_id": slave_id,
            "function_code": function_code,
            "address": address,
            "count": count,
            "raw_values": values,
            "registers": regs,
            "coils": coils,
            "hex_values": [f"0x{v:04X}" for v in regs],
            "int16_values": [(v if v < 32768 else v - 65536) for v in regs],
            "float32_be": [decoding["float32_be"]] if decoding.get("float32_be") is not None else [],
            "float32_le": [decoding["float32_le"]] if decoding.get("float32_le") is not None else [],
            "decoding": decoding,
            "simulated": True,
            "elapsed_ms": elapsed,
            "error": None,
        }

    # Interrogazione hardware reale via pymodbus
    try:
        from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    except ImportError:
        return {
            "success": False,
            "status": "error",
            "error": "Libreria pymodbus non installata.",
            "elapsed_ms": 0.0,
        }

    client = None
    try:
        if protocol.lower() == "tcp" and ip:
            client = ModbusTcpClient(host=ip, port=tcp_port, timeout=timeout)
        elif port:
            client = ModbusSerialClient(
                port=port,
                baudrate=baudrate,
                parity=parity.upper() if parity else "N",
                stopbits=stopbits,
                timeout=timeout,
            )
        else:
            return {
                "success": False,
                "status": "error",
                "error": "Specificare porta seriale (RTU) o indirizzo IP (TCP).",
                "elapsed_ms": 0.0,
            }

        if not client.connect():
            return {
                "success": False,
                "status": "error",
                "error": f"Impossibile stabilire la connessione con l'endpoint {port or ip}.",
                "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
            }

        rr = None
        if function_code == 1:
            rr = client.read_coils(address=address, count=count, slave=slave_id)
        elif function_code == 2:
            rr = client.read_discrete_inputs(address=address, count=count, slave=slave_id)
        elif function_code == 3:
            rr = client.read_holding_registers(address=address, count=count, slave=slave_id)
        elif function_code == 4:
            rr = client.read_input_registers(address=address, count=count, slave=slave_id)
        else:
            return {
                "success": False,
                "status": "error",
                "error": f"Function code Modbus non supportato per lettura: FC{function_code}.",
                "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
            }

        if rr.isError():
            return {
                "success": False,
                "status": "error",
                "error": f"Risposta di eccezione Modbus: {rr}",
                "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
            }

        raw_vals = rr.bits[:count] if hasattr(rr, "bits") else rr.registers
        decoding = decode_modbus_value(raw_vals) if function_code in (3, 4) else {}
        regs = raw_vals if function_code in (3, 4) else []
        coils = raw_vals if function_code in (1, 2) else []

        return {
            "success": True,
            "status": "ok",
            "slave_id": slave_id,
            "function_code": function_code,
            "address": address,
            "count": count,
            "raw_values": raw_vals,
            "registers": regs,
            "coils": coils,
            "hex_values": [f"0x{v:04X}" for v in regs],
            "int16_values": [(v if v < 32768 else v - 65536) for v in regs],
            "float32_be": [decoding["float32_be"]] if decoding.get("float32_be") is not None else [],
            "float32_le": [decoding["float32_le"]] if decoding.get("float32_le") is not None else [],
            "decoding": decoding,
            "simulated": False,
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
            "error": None,
        }

    except Exception as exc:
        log.error("Errore durante la lettura Modbus Quick Commander: %s", exc)
        return {
            "success": False,
            "status": "error",
            "error": str(exc),
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass


async def modbus_quick_write(
    protocol: str = "rtu",
    port: Optional[str] = None,
    baudrate: int = 9600,
    parity: str = "N",
    stopbits: int = 1,
    ip: Optional[str] = None,
    tcp_port: int = 502,
    slave_id: int = 1,
    function_code: int = 6,
    address: int = 0,
    values: Optional[list[Any]] = None,
    data_type: str = "uint16",
    timeout: float = 0.8,
) -> dict[str, Any]:
    """
    Writes registers or coils to a Modbus device (physical or simulated).
    FC 5: Write Single Coil
    FC 6: Write Single Register
    FC 15: Write Multiple Coils
    FC 16: Write Multiple Holding Registers
    """
    t0 = time.monotonic()
    values = values or [0]

    # Convert user values if encoded type specified
    if function_code in (6, 16) and len(values) == 1 and data_type in ("int16", "float32", "float32_swapped"):
        encoded_registers = encode_modbus_value(values[0], data_type)
        if len(encoded_registers) > 1:
            function_code = 16
        values = encoded_registers

    # Safe Mode Interlock
    if not simulator.is_active and not safe_mode.is_armed:
        return {
            "success": False,
            "status": "safe_mode_locked",
            "error": "Safe Mode Attivo: le manovre di forzatura su bus di campo sono bloccate. Sbloccare Safe Mode specificando Operatore e Commessa.",
            "elapsed_ms": 0.0,
        }

    operator = safe_mode.operator or ("simulator" if simulator.is_active else "field_technician")
    job_order = safe_mode.job_order or "N/A"
    target = {
        "protocol": protocol,
        "port": port,
        "ip": ip,
        "slave_id": slave_id,
        "function_code": function_code,
        "address": address,
        "count": len(values),
    }

    # Write-Ahead Log: registrazione INTENT prima della trasmissione fisica
    intent_id = audit_journal.record_intent(
        action=f"modbus_write_fc{function_code:02d}",
        protocol=f"modbus_{protocol.lower()}",
        target=target,
        value_requested=values,
        operator=operator,
        job_order=job_order,
    )

    # Se il simulatore è attivo
    if simulator.is_active:
        if function_code == 5:
            simulator.write_modbus_coil(slave_id, address, bool(values[0]))
        elif function_code == 15:
            for i, val in enumerate(values):
                simulator.write_modbus_coil(slave_id, address + i, bool(val))
        elif function_code == 6:
            simulator.write_modbus_register(slave_id, address, int(values[0]))
        elif function_code == 16:
            for i, val in enumerate(values):
                simulator.write_modbus_register(slave_id, address + i, int(val))

        elapsed = round((time.monotonic() - t0) * 1000, 1)
        audit_journal.record_result(
            intent_id=intent_id,
            action=f"modbus_write_fc{function_code:02d}",
            protocol=f"modbus_{protocol.lower()}",
            target=target,
            status="success",
            value_requested=values,
            value_verified=values,
            operator=operator,
            job_order=job_order,
            elapsed_ms=elapsed,
        )
        return {
            "success": True,
            "status": "ok",
            "audit_id": intent_id,
            "slave_id": slave_id,
            "function_code": function_code,
            "address": address,
            "written_values": values,
            "registers_written": len(values),
            "simulated": True,
            "elapsed_ms": elapsed,
            "message": f"Scrittura FC{function_code:02d} completata su slave #{slave_id} (Simulatore).",
            "error": None,
        }

    # Interrogazione hardware reale via pymodbus
    try:
        from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    except ImportError:
        err_msg = "Libreria pymodbus non installata."
        audit_journal.record_result(
            intent_id=intent_id,
            action=f"modbus_write_fc{function_code:02d}",
            protocol=f"modbus_{protocol.lower()}",
            target=target,
            status="error",
            value_requested=values,
            operator=operator,
            job_order=job_order,
            error=err_msg,
        )
        return {
            "success": False,
            "status": "error",
            "audit_id": intent_id,
            "error": err_msg,
            "elapsed_ms": 0.0,
        }

    client = None
    try:
        if protocol.lower() == "tcp" and ip:
            client = ModbusTcpClient(host=ip, port=tcp_port, timeout=timeout)
        elif port:
            client = ModbusSerialClient(
                port=port,
                baudrate=baudrate,
                parity=parity.upper() if parity else "N",
                stopbits=stopbits,
                timeout=timeout,
            )
        else:
            err_msg = "Specificare porta seriale (RTU) o indirizzo IP (TCP)."
            audit_journal.record_result(
                intent_id=intent_id,
                action=f"modbus_write_fc{function_code:02d}",
                protocol=f"modbus_{protocol.lower()}",
                target=target,
                status="error",
                value_requested=values,
                operator=operator,
                job_order=job_order,
                error=err_msg,
            )
            return {
                "success": False,
                "status": "error",
                "audit_id": intent_id,
                "error": err_msg,
                "elapsed_ms": 0.0,
            }

        if not client.connect():
            err_msg = f"Impossibile connettersi all'endpoint {port or ip}."
            audit_journal.record_result(
                intent_id=intent_id,
                action=f"modbus_write_fc{function_code:02d}",
                protocol=f"modbus_{protocol.lower()}",
                target=target,
                status="error",
                value_requested=values,
                operator=operator,
                job_order=job_order,
                elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
                error=err_msg,
            )
            return {
                "success": False,
                "status": "error",
                "audit_id": intent_id,
                "error": err_msg,
                "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
            }

        wr = None
        if function_code == 5:
            wr = client.write_coil(address=address, value=bool(values[0]), slave=slave_id)
        elif function_code == 6:
            wr = client.write_register(address=address, value=int(values[0]) & 0xFFFF, slave=slave_id)
        elif function_code == 15:
            coil_bools = [bool(v) for v in values]
            wr = client.write_coils(address=address, values=coil_bools, slave=slave_id)
        elif function_code == 16:
            reg_ints = [int(v) & 0xFFFF for v in values]
            wr = client.write_registers(address=address, values=reg_ints, slave=slave_id)
        else:
            err_msg = f"Function code Modbus non supportato per scrittura: FC{function_code}."
            audit_journal.record_result(
                intent_id=intent_id,
                action=f"modbus_write_fc{function_code:02d}",
                protocol=f"modbus_{protocol.lower()}",
                target=target,
                status="error",
                value_requested=values,
                operator=operator,
                job_order=job_order,
                elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
                error=err_msg,
            )
            return {
                "success": False,
                "status": "error",
                "audit_id": intent_id,
                "error": err_msg,
                "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
            }

        if wr.isError():
            err_msg = f"Eccezione Modbus durante la forzatura: {wr}"
            audit_journal.record_result(
                intent_id=intent_id,
                action=f"modbus_write_fc{function_code:02d}",
                protocol=f"modbus_{protocol.lower()}",
                target=target,
                status="error",
                value_requested=values,
                operator=operator,
                job_order=job_order,
                elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
                error=err_msg,
            )
            return {
                "success": False,
                "status": "error",
                "audit_id": intent_id,
                "error": err_msg,
                "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
            }

        elapsed = round((time.monotonic() - t0) * 1000, 1)
        audit_journal.record_result(
            intent_id=intent_id,
            action=f"modbus_write_fc{function_code:02d}",
            protocol=f"modbus_{protocol.lower()}",
            target=target,
            status="success",
            value_requested=values,
            value_verified=values,
            operator=operator,
            job_order=job_order,
            elapsed_ms=elapsed,
        )
        return {
            "success": True,
            "status": "ok",
            "audit_id": intent_id,
            "slave_id": slave_id,
            "function_code": function_code,
            "address": address,
            "written_values": values,
            "registers_written": len(values),
            "simulated": False,
            "elapsed_ms": elapsed,
            "message": f"Forzatura FC{function_code:02d} completata con successo su slave #{slave_id}.",
            "error": None,
        }

    except Exception as exc:
        err_msg = str(exc)
        log.error("Errore durante la scrittura Modbus: %s", exc)
        audit_journal.record_result(
            intent_id=intent_id,
            action=f"modbus_write_fc{function_code:02d}",
            protocol=f"modbus_{protocol.lower()}",
            target=target,
            status="error",
            value_requested=values,
            operator=operator,
            job_order=job_order,
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
            error=err_msg,
        )
        return {
            "success": False,
            "status": "error",
            "audit_id": intent_id,
            "error": err_msg,
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass


# ── BACnet Point Commander Execution ──────────────────────────────────────────

async def bacnet_point_override(
    device_id: int,
    address: Optional[str] = None,
    object_type: str = "analogOutput",
    instance: int = 1,
    value: Any = None,
    priority: int = 8,
    relinquish: bool = False,
    timeout: float = 2.0,
) -> dict[str, Any]:
    """
    Overrides presentValue on a BACnet object with Priority Array support (default Priority 8).
    Supports Relinquish (relinquish=True or value=None) to release the override.
    """
    t0 = time.monotonic()
    priority = max(1, min(16, priority))
    is_relinquish = relinquish or (value is None)
    is_sim = simulator.is_active and (device_id in (1001, 1002))

    # Safe Mode Interlock
    if not is_sim and not safe_mode.is_armed:
        return {
            "success": False,
            "status": "safe_mode_locked",
            "error": "Safe Mode Attivo: le forzature BACnet su bus di campo sono bloccate. Sbloccare Safe Mode specificando Operatore e Commessa.",
            "elapsed_ms": 0.0,
        }

    operator = safe_mode.operator or ("simulator" if is_sim else "field_technician")
    job_order = safe_mode.job_order or "N/A"
    action_name = "bacnet_relinquish" if is_relinquish else "bacnet_override"
    target = {
        "device_id": device_id,
        "address": address or "auto",
        "object": f"{object_type}:{instance}",
        "priority": priority,
    }

    # Write-Ahead Log: registrazione INTENT prima della trasmissione
    intent_id = audit_journal.record_intent(
        action=action_name,
        protocol="bacnet_ip",
        target=target,
        value_requested=None if is_relinquish else value,
        operator=operator,
        job_order=job_order,
    )

    # Gestione device simulato in Demo Mode
    if is_sim:
        target_val = None if is_relinquish else value
        simulator.override_bacnet_point(device_id, object_type, instance, target_val, priority)
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        action_desc = f"Relinquish (rilascio priorità {priority})" if is_relinquish else f"Forzatura a {value} (priorità {priority})"
        audit_journal.record_result(
            intent_id=intent_id,
            action=action_name,
            protocol="bacnet_ip",
            target=target,
            status="success",
            value_requested=None if is_relinquish else value,
            value_verified=target_val,
            operator=operator,
            job_order=job_order,
            elapsed_ms=elapsed,
        )
        return {
            "success": True,
            "status": "ok",
            "audit_id": intent_id,
            "device_id": device_id,
            "object_identifier": f"{object_type}:{instance}",
            "object_type": object_type,
            "instance": instance,
            "value": str(target_val) if target_val is not None else None,
            "written_value": target_val,
            "priority": priority,
            "relinquish": is_relinquish,
            "relinquished": is_relinquish,
            "simulated": True,
            "elapsed_ms": elapsed,
            "message": f"BACnet {action_desc} completata su {object_type}:{instance} (Simulatore).",
            "error": None,
        }

    # Interrogazione su rete BACnet/IP reale
    try:
        from bacpypes3.app import Application
        from bacpypes3.pdu import Address
        from bacpypes3.primitivedata import Null, Real, CharacterString, Boolean, Unsigned
        from scanners.bacnet import _make_application, _safe_close
    except ImportError:
        err_msg = "Libreria bacpypes3 non installata."
        audit_journal.record_result(
            intent_id=intent_id,
            action=action_name,
            protocol="bacnet_ip",
            target=target,
            status="error",
            value_requested=None if is_relinquish else value,
            operator=operator,
            job_order=job_order,
            error=err_msg,
        )
        return {
            "success": False,
            "status": "error",
            "audit_id": intent_id,
            "error": err_msg,
            "elapsed_ms": 0.0,
        }

    # Recupera indirizzo se non fornito
    target_addr = address
    if not target_addr:
        from data.state import state
        dev = state.bacnet_devices.get(device_id)
        if dev and dev.address:
            target_addr = dev.address

    if not target_addr:
        err_msg = f"Indirizzo di rete non disponibile per il device {device_id}."
        audit_journal.record_result(
            intent_id=intent_id,
            action=action_name,
            protocol="bacnet_ip",
            target=target,
            status="error",
            value_requested=None if is_relinquish else value,
            operator=operator,
            job_order=job_order,
            error=err_msg,
        )
        return {
            "success": False,
            "status": "error",
            "audit_id": intent_id,
            "error": err_msg,
            "elapsed_ms": 0.0,
        }

    app = None
    try:
        app = _make_application()
        target_pdu = Address(target_addr)
        obj_ident = f"{object_type},{instance}"

        # Valore BACnet tipizzato
        val_to_write: Any
        if is_relinquish:
            val_to_write = Null()
        elif "binary" in object_type.lower():
            val_to_write = Boolean(bool(value) or str(value).lower() in ("1", "true", "active"))
        elif "analog" in object_type.lower():
            val_to_write = Real(float(value))
        elif "multistate" in object_type.lower():
            val_to_write = Unsigned(int(value))
        else:
            val_to_write = CharacterString(str(value))

        await asyncio.wait_for(
            app.write_property(
                target_pdu,
                obj_ident,
                "present-value",
                val_to_write,
                priority=priority,
            ),
            timeout=timeout,
        )

        elapsed = round((time.monotonic() - t0) * 1000, 1)
        action_desc = f"Relinquish priorità {priority}" if is_relinquish else f"Forzatura a '{value}' (priorità {priority})"
        audit_journal.record_result(
            intent_id=intent_id,
            action=action_name,
            protocol="bacnet_ip",
            target=target,
            status="success",
            value_requested=None if is_relinquish else value,
            value_verified=None if is_relinquish else value,
            operator=operator,
            job_order=job_order,
            elapsed_ms=elapsed,
        )
        return {
            "success": True,
            "status": "ok",
            "audit_id": intent_id,
            "device_id": device_id,
            "object_identifier": f"{object_type}:{instance}",
            "object_type": object_type,
            "instance": instance,
            "value": None if is_relinquish else str(value),
            "written_value": None if is_relinquish else value,
            "priority": priority,
            "relinquish": is_relinquish,
            "relinquished": is_relinquish,
            "simulated": False,
            "elapsed_ms": elapsed,
            "message": f"Comando BACnet {action_desc} inviato con successo a {target_addr}.",
            "error": None,
        }

    except Exception as exc:
        err_msg = str(exc)
        log.error("Errore durante l'override BACnet: %s", exc)
        audit_journal.record_result(
            intent_id=intent_id,
            action=action_name,
            protocol="bacnet_ip",
            target=target,
            status="error",
            value_requested=None if is_relinquish else value,
            operator=operator,
            job_order=job_order,
            elapsed_ms=round((time.monotonic() - t0) * 1000, 1),
            error=err_msg,
        )
        return {
            "success": False,
            "status": "error",
            "audit_id": intent_id,
            "error": err_msg,
            "elapsed_ms": round((time.monotonic() - t0) * 1000, 1),
        }
    finally:
        if app:
            try:
                _safe_close(app)
            except Exception:
                pass


# ── Modbus Stress Test & Bus Latency Benchmark ────────────────────────────────

async def modbus_benchmark(
    protocol: str = "rtu",
    port: Optional[str] = None,
    baudrate: int = 9600,
    parity: str = "N",
    stopbits: int = 1,
    ip: Optional[str] = None,
    tcp_port: int = 502,
    slave_id: int = 1,
    address: int = 0,
    count: int = 1,
    iterations: int = 20,
    timeout: float = 0.5,
) -> dict[str, Any]:
    """
    Esegue un benchmark e stress-test di comunicazione su un nodo Modbus (RTU o TCP).
    Invia 'iterations' frame di lettura consecutivi (FC03/FC04), misura latenza al ms di ciascun pacchetto,
    calcola Min, Max, Media, Jitter (deviazione standard) e Frame Error Rate (FER %).
    Formula un verdetto ingegneristico sulla qualità fisica della linea/bus.
    """
    iterations = max(5, min(int(iterations or 20), 100))
    latencies: list[float] = []
    errors: list[str] = []
    success_count = 0
    fail_count = 0

    t_start = time.monotonic()

    for i in range(iterations):
        res = await modbus_quick_read(
            protocol=protocol,
            port=port,
            baudrate=baudrate,
            parity=parity,
            stopbits=stopbits,
            ip=ip,
            tcp_port=tcp_port,
            slave_id=slave_id,
            function_code=3,
            address=address,
            count=count,
            timeout=timeout,
        )
        if res.get("success"):
            success_count += 1
            latencies.append(float(res.get("elapsed_ms", 0.0)))
        else:
            fail_count += 1
            latencies.append(round(timeout * 1000, 1))
            err = res.get("error") or "Timeout / Eccezione"
            if err not in errors:
                errors.append(err)
        # Breve pausa per evitare saturazione buffer su RTU lenta
        await asyncio.sleep(0.01)

    total_elapsed = round((time.monotonic() - t_start) * 1000, 1)

    # Calcolo metriche statistiche
    fer_pct = round((fail_count / iterations) * 100.0, 1)

    if latencies:
        min_lat = round(min(latencies), 1)
        max_lat = round(max(latencies), 1)
        avg_lat = round(sum(latencies) / len(latencies), 1)
        variance = sum((x - avg_lat) ** 2 for x in latencies) / len(latencies)
        jitter = round(variance ** 0.5, 1)
    else:
        min_lat = max_lat = avg_lat = jitter = 0.0

    # Diagnosi e Verdetto Ingegneristico
    if fer_pct == 0.0:
        if avg_lat < 80.0 and jitter < 15.0:
            rating = "EXCELLENT"
            rating_it = "ECCELLENTE"
            diagnosis = "Bus ottimale: nessuna perdita di frame, latenza minima e jitter trascurabile."
        elif avg_lat < 180.0:
            rating = "GOOD"
            rating_it = "BUONO"
            diagnosis = "Comunicazione stabile e affidabile con tempi di risposta nella norma industriale."
        else:
            rating = "DEGRADED"
            rating_it = "DEGRADATO"
            diagnosis = "Nessun errore di frame ma latenza media elevata (>180ms): verificare lunghezza cavo o carico dello slave."
    elif fer_pct <= 5.0:
        rating = "DEGRADED"
        rating_it = "DEGRADATO"
        diagnosis = f"Perdita sporadica di pacchetti (FER {fer_pct}%): possibili disturbi EMI, terminazione 120Ω mancante o timeout troppo stretto."
    else:
        rating = "CRITICAL"
        rating_it = "CRITICO"
        diagnosis = f"Qualità del bus critica (FER {fer_pct}%): frequenti timeout o scarti CRC. Verificare cablaggio A/B, schermatura, o conflitto indirizzi ID {slave_id}."

    return {
        "success": True,
        "protocol": protocol.lower(),
        "target": {
            "port": port,
            "ip": ip,
            "slave_id": slave_id,
            "baudrate": baudrate,
            "iterations": iterations,
        },
        "iterations": iterations,
        "success_count": success_count,
        "fail_count": fail_count,
        "packet_error_rate_pct": fer_pct,
        "min_latency_ms": min_lat,
        "max_latency_ms": max_lat,
        "avg_latency_ms": avg_lat,
        "jitter_ms": jitter,
        "rating": rating,
        "rating_label": rating_it,
        "diagnosis": diagnosis,
        "latencies": latencies,
        "errors": errors,
        "total_elapsed_ms": total_elapsed,
    }

