"""
BHAM – Virtual Plant Simulator (Demo / Offline Mode)
===================================================
Provides synthetic BACS/HVAC plant simulation for testing, demonstrations,
and offline commissioning without requiring physical bus connections.

Simulated Assets:
- Modbus RTU Slave 1: Water-cooled Chiller (Temperatures, setpoints, coils)
- Modbus RTU Slave 2: Primary Variable-Speed Pump (Hz, flow, pressure)
- Modbus TCP Slave 3 (192.168.1.50:502): Main Switchboard Multi-function Meter
- BACnet/IP Device 1001 (192.168.1.100): Office AHU / UTA 01 (Air handling unit)
- BACnet/IP Device 1002 (192.168.1.101): North Zone VAV Terminal Box
- KNXnet/IP 1.1.1 & 1.1.2: DALI Gateway & Touch Thermostat
- L2 ARP Network Hosts: Cisco Gateway, Siemens S7 PLC, Tridium Niagara JACE
"""

from __future__ import annotations

import asyncio
import math
import random
import time
from typing import Any, Optional, Union

from core.logger import logger
from data.models import (
    BACnetDevice,
    IPHost,
    KNXDevice,
    ModbusDevice,
    Parity,
    Protocol,
    SerialParams,
)
from data.state import state

log = logger.getChild("simulator")


class PlantSimulator:
    """Singleton virtual plant engine with dynamic synthetic telemetry."""

    def __init__(self) -> None:
        self._active: bool = False
        self._sim_task: Optional[asyncio.Task] = None
        self._start_time: float = 0.0

        # Memory stores for simulated devices
        self._modbus_registers: dict[int, dict[int, int]] = {
            1: {  # Slave 1: Chiller
                0: 1,      # Status (1=RUN)
                1: 0,      # Alarm Code (0=OK)
                2: 72,     # Evaporator Outlet: 7.2°C (x10)
                3: 121,    # Evaporator Inlet: 12.1°C (x10)
                4: 70,     # Setpoint: 7.0°C (x10)
                5: 145,    # Refrigerant pressure: 14.5 bar (x10)
            },
            2: {  # Slave 2: Pump
                0: 1,      # Status (1=RUN)
                1: 425,    # Inverter frequency: 42.5 Hz (x10)
                2: 28,     # Delivery pressure: 2.8 bar (x10)
                3: 453,    # Flow rate: 45.3 m3/h (x10)
                4: 35,     # Active Power: 3.5 kW (x10)
            },
            3: {  # Slave 3: Power Meter
                0: 0x4366, # Voltage L1-N (Float32 MSW 230.5V)
                1: 0x8000, # LSW
                2: 0x4234, # Current L1 (Float32 MSW 45.2A)
                3: 0xCCD0, # LSW
                4: 0x426A, # Active Power kW (Float32 MSW 58.7 kW)
                5: 0xCCD0, # LSW
                6: 0x480B, # Total Energy kWh (Float32 MSW 142850 kWh)
                7: 0x9240, # LSW
            },
        }

        self._modbus_coils: dict[int, dict[int, bool]] = {
            1: {0: True, 1: True, 2: False, 3: False},  # Chiller Run, Comp1, Comp2, Alarm
            2: {0: True, 1: True, 2: False},            # Pump Start, Ready, Fault
        }

        self._bacnet_objects: dict[int, list[dict[str, Any]]] = {}
        self._bacnet_overrides: dict[str, dict[int, Any]] = {}  # "dev_id:type:inst" -> {priority: val}
        self._virtual_modbus_keys: set[str] = set()
        self._virtual_bacnet_keys: set[int] = set()
        self._virtual_knx_keys: set[str] = set()
        self._virtual_ip_keys: set[str] = set()

    @property
    def is_active(self) -> bool:
        return self._active

    def get_status(self) -> dict[str, Any]:
        summary = {
            "modbus_slaves": len(self._virtual_modbus_keys),
            "bacnet_devices": len(self._virtual_bacnet_keys),
            "knx_devices": len(self._virtual_knx_keys),
            "ip_hosts": len(self._virtual_ip_keys),
        } if self._active else {"modbus_slaves": 0, "bacnet_devices": 0, "knx_devices": 0, "ip_hosts": 0}

        return {
            "active": self._active,
            "uptime_seconds": round(time.monotonic() - self._start_time, 1) if self._active else 0.0,
            "devices_count": (
                len(self._virtual_modbus_keys) + len(self._virtual_bacnet_keys) +
                len(self._virtual_knx_keys) + len(self._virtual_ip_keys)
            ) if self._active else 0,
            "summary": summary,
        }

    async def start(self) -> None:
        """Start the virtual plant simulator."""
        if self._active:
            return
        self._active = True
        self._start_time = time.monotonic()
        log.info("═══ Virtual Plant Simulator STARTED (Demo Mode ON) ═══")

        self._populate_virtual_devices()

        loop = asyncio.get_running_loop()
        self._sim_task = loop.create_task(self._simulation_loop(), name="plant-simulator")

        # Broadcast update
        from api.websockets import manager
        manager.broadcast_sync({
            "event": "demo_status_changed",
            "active": True,
            "message": "Modalità Demo Attiva: Dispositivi virtuali BACS caricati."
        })

    async def stop(self) -> None:
        """Stop the virtual plant simulator."""
        if not self._active:
            return
        self._active = False
        if self._sim_task and not self._sim_task.done():
            self._sim_task.cancel()
            try:
                await self._sim_task
            except asyncio.CancelledError:
                pass
        self._sim_task = None

        # Clean up virtual devices from state
        for mk in self._virtual_modbus_keys:
            state.modbus_devices.pop(mk, None)
        for bk in self._virtual_bacnet_keys:
            state.bacnet_devices.pop(bk, None)
        for kk in self._virtual_knx_keys:
            state.knx_devices.pop(kk, None)
        for ik in self._virtual_ip_keys:
            state.ip_hosts.pop(ik, None)
        self._virtual_modbus_keys.clear()
        self._virtual_bacnet_keys.clear()
        self._virtual_knx_keys.clear()
        self._virtual_ip_keys.clear()

        log.info("═══ Virtual Plant Simulator STOPPED (Demo Mode OFF) ═══")

        from api.websockets import manager
        manager.broadcast_sync({
            "event": "demo_status_changed",
            "active": False,
            "message": "Modalità Demo Disattivata."
        })

    async def toggle(self) -> bool:
        """Toggle demo mode ON/OFF."""
        if self._active:
            await self.stop()
            return False
        else:
            await self.start()
            return True

    # ── Population ────────────────────────────────────────────────────────────

    def _populate_virtual_devices(self) -> None:
        """Populate AppState with realistic virtual devices."""
        # 1. Modbus RTU Slaves
        serial_p = SerialParams(port="/dev/ttyUSB0", baudrate=9600, parity=Parity.NONE, stopbits=1)
        chiller_regs = [
            {"address": 0, "type": "holding", "raw_dec": 1, "raw_hex": "0x0001", "label": "Chiller Unit Status"},
            {"address": 1, "type": "holding", "raw_dec": 0, "raw_hex": "0x0000", "label": "Active Alarm Code"},
            {"address": 2, "type": "holding", "raw_dec": 72, "raw_hex": "0x0048", "label": "Temp Mandata Evap (°C/10)"},
            {"address": 3, "type": "holding", "raw_dec": 121, "raw_hex": "0x0079", "label": "Temp Ritorno Evap (°C/10)"},
            {"address": 4, "type": "holding", "raw_dec": 70, "raw_hex": "0x0046", "label": "Setpoint Mandata (°C/10)"},
            {"address": 5, "type": "holding", "raw_dec": 145, "raw_hex": "0x0091", "label": "Pressione R410A (bar/10)"},
        ]
        chiller = ModbusDevice(
            protocol=Protocol.MODBUS_RTU,
            slave_id=1,
            serial_params=serial_p,
            tags=["virtual", "chiller", "Climaveneta FOC/W 0452 Chiller"],
            registers={str(r["address"]): r for r in chiller_regs},
        )
        state.upsert_modbus(chiller)

        pump_regs = [
            {"address": 0, "type": "holding", "raw_dec": 1, "raw_hex": "0x0001", "label": "Pump Run State"},
            {"address": 1, "type": "holding", "raw_dec": 425, "raw_hex": "0x01A9", "label": "Frequenza Inverter (Hz/10)"},
            {"address": 2, "type": "holding", "raw_dec": 28, "raw_hex": "0x001C", "label": "Pressione Differenziale (bar/10)"},
            {"address": 3, "type": "holding", "raw_dec": 453, "raw_hex": "0x01C5", "label": "Portata Idraulica (m3h/10)"},
            {"address": 4, "type": "holding", "raw_dec": 35, "raw_hex": "0x0023", "label": "Potenza Assorbita (kW/10)"},
        ]
        pump = ModbusDevice(
            protocol=Protocol.MODBUS_RTU,
            slave_id=2,
            serial_params=serial_p,
            tags=["virtual", "pump", "Grundfos Magna3 65-150 Inverter Pump"],
            registers={str(r["address"]): r for r in pump_regs},
        )
        state.upsert_modbus(pump)

        # 2. Modbus TCP Power Meter
        pm_regs = [
            {"address": 0, "type": "holding", "raw_dec": 0x4366, "raw_hex": "0x4366", "float32": 230.5, "label": "Voltage L1-N"},
            {"address": 2, "type": "holding", "raw_dec": 0x4234, "raw_hex": "0x4234", "float32": 45.2, "label": "Current L1"},
            {"address": 4, "type": "holding", "raw_dec": 0x426A, "raw_hex": "0x426A", "float32": 58.7, "label": "Total Active Power kW"},
            {"address": 6, "type": "holding", "raw_dec": 0x480B, "raw_hex": "0x480B", "float32": 142850.0, "label": "Total Active Energy kWh"},
        ]
        pm = ModbusDevice(
            protocol=Protocol.MODBUS_TCP,
            slave_id=1,
            ip="192.168.1.50",
            tcp_port=502,
            tags=["virtual", "power_meter", "Schneider Electric PM5350 Power Meter"],
            registers={str(r["address"]): r for r in pm_regs},
        )
        state.upsert_modbus(pm)

        # 3. BACnet/IP Devices
        ahu_objects = [
            {"identifier": "analogInput:1", "type": "analogInput", "instance": 1, "name": "Temp Mandata Aria", "present_value": "21.4", "units": "°C"},
            {"identifier": "analogInput:2", "type": "analogInput", "instance": 2, "name": "Temp Ripresa Aria", "present_value": "23.8", "units": "°C"},
            {"identifier": "analogInput:3", "type": "analogInput", "instance": 3, "name": "Temp Aria Esterna", "present_value": "16.5", "units": "°C"},
            {"identifier": "analogInput:4", "type": "analogInput", "instance": 4, "name": "Pressione Canale Mandata", "present_value": "248.0", "units": "Pa"},
            {"identifier": "analogOutput:1", "type": "analogOutput", "instance": 1, "name": "Serranda Aria Esterna", "present_value": "35.0", "units": "%"},
            {"identifier": "analogOutput:2", "type": "analogOutput", "instance": 2, "name": "Valvola Batteria Calda", "present_value": "12.0", "units": "%"},
            {"identifier": "analogOutput:3", "type": "analogOutput", "instance": 3, "name": "Valvola Batteria Fredda", "present_value": "0.0", "units": "%"},
            {"identifier": "binaryInput:1", "type": "binaryInput", "instance": 1, "name": "Allarme Antigelo Termostato", "present_value": "inactive", "units": ""},
            {"identifier": "binaryInput:2", "type": "binaryInput", "instance": 2, "name": "Pressostato Differenziale Filtri", "present_value": "inactive", "units": ""},
            {"identifier": "binaryOutput:1", "type": "binaryOutput", "instance": 1, "name": "Comando Ventilatore Mandata", "present_value": "active", "units": ""},
            {"identifier": "binaryOutput:2", "type": "binaryOutput", "instance": 2, "name": "Comando Ventilatore Ripresa", "present_value": "active", "units": ""},
            {"identifier": "analogValue:1", "type": "analogValue", "instance": 1, "name": "Setpoint Comfort Mandata", "present_value": "21.5", "units": "°C"},
        ]
        self._bacnet_objects[1001] = ahu_objects

        ahu = BACnetDevice(
            device_id=1001,
            address="192.168.1.100:47808",
            network=1,
            protocol=Protocol.BACNET_IP,
            vendor_name="Trane Technologies",
            vendor_id=2,
            model_name="Tracer SC+ AHU Controller",
            firmware_revision="v5.20.108",
            object_name="UTA_01_OFFICES",
            object_list=ahu_objects,
        )
        state.upsert_bacnet(ahu)

        vav_objects = [
            {"identifier": "analogInput:1", "type": "analogInput", "instance": 1, "name": "Temp Ambiente Zona Nord", "present_value": "22.3", "units": "°C"},
            {"identifier": "analogInput:2", "type": "analogInput", "instance": 2, "name": "Portata Aria Attuale VAV", "present_value": "315.0", "units": "m³/h"},
            {"identifier": "analogOutput:1", "type": "analogOutput", "instance": 1, "name": "Posizione Attuatore VAV", "present_value": "45.0", "units": "%"},
            {"identifier": "analogValue:1", "type": "analogValue", "instance": 1, "name": "Setpoint Temperatura Zona", "present_value": "22.0", "units": "°C"},
        ]
        self._bacnet_objects[1002] = vav_objects

        vav = BACnetDevice(
            device_id=1002,
            address="192.168.1.101:47808",
            network=1,
            protocol=Protocol.BACNET_IP,
            vendor_name="Johnson Controls",
            vendor_id=5,
            model_name="Metasys FX-PCV1615 VAV Controller",
            firmware_revision="v8.1.2",
            object_name="VAV_ZONE_NORTH_01",
            object_list=vav_objects,
        )
        state.upsert_bacnet(vav)

        # 4. KNXnet/IP Devices
        knx1 = KNXDevice(
            ip_address="192.168.1.80",
            port=3671,
            individual_address="1.1.1",
            device_name="Siemens 5WG1 141-1AB03 DALI Gateway Plus",
            medium="IP",
        )
        state.upsert_knx(knx1)

        knx2 = KNXDevice(
            ip_address="192.168.1.81",
            port=3671,
            individual_address="1.1.2",
            device_name="Zennio Z41 Touch Screen Thermostat",
            medium="TP1",
        )
        state.upsert_knx(knx2)

        # 5. IP Hosts (BACS Network Discovery)
        from core.oui_lookup import get_vendor_by_mac
        hosts = [
            IPHost(
                ip="192.168.1.1",
                mac="00:0c:29:4f:8e:11",
                vendor=get_vendor_by_mac("00:0c:29:4f:8e:11"),
                hostname="gw-core-lan01",
                hostname_source="dns",
                open_ports=[80, 443],
                services={80: "HTTP (PLC/BMS Web)", 443: "HTTPS (Secure PLC/BMS)"},
                response_time_ms=1.2,
            ),
            IPHost(
                ip="192.168.1.10",
                mac="00:1c:06:12:34:56",
                vendor=get_vendor_by_mac("00:1c:06:12:34:56"),
                hostname="plc-simatic-s7-1200",
                hostname_source="netbios",
                open_ports=[80, 502, 47808],
                services={80: "HTTP (PLC/BMS Web)", 502: "Modbus TCP", 47808: "BACnet/IP"},
                response_time_ms=3.5,
                protocol_hints=[Protocol.MODBUS_TCP, Protocol.BACNET_IP],
            ),
            IPHost(
                ip="192.168.1.20",
                mac="00:50:f1:aa:bb:cc",
                vendor=get_vendor_by_mac("00:50:f1:aa:bb:cc"),
                hostname="jace-8000-niagara4",
                hostname_source="netbios",
                open_ports=[80, 443, 1911, 8443],
                services={80: "HTTP (PLC/BMS Web)", 443: "HTTPS (Secure PLC/BMS)", 1911: "Niagara Fox Native", 8443: "HTTPS-Alt / Niagara Fox Secure"},
                response_time_ms=4.8,
            ),
            IPHost(
                ip="192.168.1.50",
                mac="00:80:f4:33:22:11",
                vendor=get_vendor_by_mac("00:80:f4:33:22:11"),
                hostname="pm5350-switchboard",
                hostname_source="dns",
                open_ports=[80, 502],
                services={80: "HTTP (PLC/BMS Web)", 502: "Modbus TCP"},
                response_time_ms=2.1,
                protocol_hints=[Protocol.MODBUS_TCP],
            ),
            IPHost(
                ip="192.168.1.100",
                mac="00:10:e0:55:66:77",
                vendor=get_vendor_by_mac("00:10:e0:55:66:77"),
                hostname="tracer-sc-ahu01",
                hostname_source="dns",
                open_ports=[80, 47808],
                services={80: "HTTP (PLC/BMS Web)", 47808: "BACnet/IP"},
                response_time_ms=5.4,
                protocol_hints=[Protocol.BACNET_IP],
            ),
        ]
        for h in hosts:
            state.upsert_ip_host(h)

        self._virtual_modbus_keys = {
            f"{serial_p.port}-{chiller.slave_id}",
            f"{serial_p.port}-{pump.slave_id}",
            f"{pm.ip}-{pm.slave_id}",
        }
        self._virtual_bacnet_keys = {ahu.device_id, vav.device_id}
        self._virtual_knx_keys = {f"{knx1.ip_address}:{knx1.individual_address}", f"{knx2.ip_address}:{knx2.individual_address}"}
        self._virtual_ip_keys = {h.ip for h in hosts}

        log.info(
            "Virtual Plant popolato con successo: 3 Modbus, 2 BACnet (%d oggetti), 2 KNX, 5 Host IP",
            len(ahu_objects) + len(vav_objects)
        )

    # ── Dynamic Simulation Loop ───────────────────────────────────────────────

    async def _simulation_loop(self) -> None:
        """Background coroutine that oscillates synthetic telemetry for a live feeling."""
        step = 0
        from api.websockets import manager

        while self._active:
            try:
                await asyncio.sleep(2.0)
                step += 1
                t = time.monotonic()

                # Oscillazione temperature chiller (sinusoide ±0.4°C)
                t_evap_out = round(7.2 + 0.3 * math.sin(step * 0.15) + random.uniform(-0.05, 0.05), 1)
                t_evap_in = round(t_evap_out + 4.8 + 0.1 * math.cos(step * 0.1), 1)
                self._modbus_registers[1][2] = int(t_evap_out * 10)
                self._modbus_registers[1][3] = int(t_evap_in * 10)

                chiller = state.modbus_devices.get("/dev/ttyUSB0:1")
                if chiller:
                    if "2" in chiller.registers:
                        chiller.registers["2"]["raw_dec"] = int(t_evap_out * 10)
                        chiller.registers["2"]["raw_hex"] = f"0x{(int(t_evap_out * 10)):04X}"
                    if "3" in chiller.registers:
                        chiller.registers["3"]["raw_dec"] = int(t_evap_in * 10)
                        chiller.registers["3"]["raw_hex"] = f"0x{(int(t_evap_in * 10)):04X}"
                    state.upsert_modbus(chiller)

                # Oscillazione potenza meter (58kW ± 1.5kW)
                power_kw = round(58.7 + 1.2 * math.sin(step * 0.2) + random.uniform(-0.3, 0.3), 1)
                pm = state.modbus_devices.get("192.168.1.50:502:1")
                if pm:
                    state.upsert_modbus(pm)

                # Aggiornamento oggetti BACnet UTA 01
                ahu = state.bacnet_devices.get(1001)
                if ahu:
                    t_mandata = round(21.4 + 0.25 * math.sin(step * 0.1), 1)
                    t_ripresa = round(23.8 + 0.15 * math.cos(step * 0.08), 1)
                    p_canale = round(248.0 + 8.0 * math.sin(step * 0.25), 1)

                    # Verifica se l'oggetto è in override manuale
                    ov_key = "1001:analogInput:1"
                    if ov_key in self._bacnet_overrides and self._bacnet_overrides[ov_key]:
                        # usa il valore a più alta priorità
                        highest_p = min(self._bacnet_overrides[ov_key].keys())
                        t_mandata = self._bacnet_overrides[ov_key][highest_p]

                    for obj in ahu.object_list:
                        if obj["identifier"] == "analogInput:1":
                            obj["present_value"] = str(t_mandata)
                        elif obj["identifier"] == "analogInput:2":
                            obj["present_value"] = str(t_ripresa)
                        elif obj["identifier"] == "analogInput:4":
                            obj["present_value"] = str(p_canale)
                    state.upsert_bacnet(ahu)

                # Notifica periodica WebSocket per refresh grafi
                if step % 5 == 0:
                    manager.broadcast_sync({
                        "event": "telemetry_pulse",
                        "timestamp": t,
                        "plant": "simulated",
                    })

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.debug("Errore nel loop di simulazione: %s", e)

    # ── Simulation Accessors for Field Tools ──────────────────────────────────

    def read_modbus_register(self, slave_id: int, address: int) -> int:
        slave_map = self._modbus_registers.get(slave_id, {})
        return slave_map.get(address, 0)

    def read_modbus_registers(self, slave_id: int, fc: int = 3, address: int = 0, count: int = 1) -> list[int]:
        return [self.read_modbus_register(slave_id, address + i) for i in range(count)]

    def write_modbus_register(
        self,
        slave_id: int,
        address: int,
        val: Optional[Union[int, list[int]]] = None,
        *,
        values: Optional[Union[int, list[int]]] = None,
    ) -> bool:
        target = values if values is not None else val
        if target is None:
            return False
        if isinstance(target, (list, tuple)):
            for i, v in enumerate(target):
                self.write_modbus_register(slave_id, address + i, v)
            return True

        if slave_id not in self._modbus_registers:
            self._modbus_registers[slave_id] = {}
        self._modbus_registers[slave_id][address] = target & 0xFFFF

        # Aggiorna lo stato in AppState
        for d in state.modbus_devices.values():
            if d.slave_id == slave_id:
                addr_key = str(address)
                if addr_key in d.registers:
                    d.registers[addr_key]["raw_dec"] = target & 0xFFFF
                    d.registers[addr_key]["raw_hex"] = f"0x{(target & 0xFFFF):04X}"
                state.upsert_modbus(d)
                break
        return True

    def read_modbus_coil(self, slave_id: int, address: int) -> bool:
        slave_coils = self._modbus_coils.get(slave_id, {})
        return slave_coils.get(address, False)

    def write_modbus_coil(self, slave_id: int, address: int, val: bool) -> bool:
        if slave_id not in self._modbus_coils:
            self._modbus_coils[slave_id] = {}
        self._modbus_coils[slave_id][address] = bool(val)
        return True

    def get_bacnet_objects(self, device_id: int) -> list[dict[str, Any]]:
        dev = state.bacnet_devices.get(device_id)
        if dev and dev.object_list:
            return dev.object_list
        return self._bacnet_objects.get(device_id, [])

    def override_bacnet_point(
        self, device_id: int, object_type: str, instance: int, value: Any, priority: int = 8
    ) -> bool:
        key = f"{device_id}:{object_type}:{instance}"
        if key not in self._bacnet_overrides:
            self._bacnet_overrides[key] = {}

        if value is None:
            # Relinquish
            self._bacnet_overrides[key].pop(priority, None)
        else:
            self._bacnet_overrides[key][priority] = value

        # Aggiorna in AppState
        dev = state.bacnet_devices.get(device_id)
        if dev:
            ident = f"{object_type}:{instance}"
            new_val = None
            if self._bacnet_overrides[key]:
                hp = min(self._bacnet_overrides[key].keys())
                new_val = self._bacnet_overrides[key][hp]
            else:
                # restore default
                for o in self._bacnet_objects.get(device_id, []):
                    if o["identifier"] == ident:
                        new_val = o["present_value"]
                        break

            for obj in dev.object_list:
                if obj["identifier"] == ident:
                    obj["present_value"] = new_val if new_val is not None else value
                    break
            state.upsert_bacnet(dev)
        return True

    def relinquish_bacnet_point(
        self, device_id: int, object_type: str, instance: int, priority: int = 8
    ) -> bool:
        return self.override_bacnet_point(device_id, object_type, instance, value=None, priority=priority)


# Global singleton instance
simulator = PlantSimulator()
