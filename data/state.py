"""
BHAM – In-Memory Application State
Single shared singleton; all mutations must go through its methods to keep
the WebSocket broadcast pipeline consistent.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from core.config import DEFAULT_SERIAL_PORT
from data.models import (
    BACnetDevice,
    BusHealth,
    IPHost,
    KNXDevice,
    ModbusDevice,
    ScanSession,
    ScanStatus,
    Protocol,
    SerialFrame,
    SessionConfig,
)

log = logging.getLogger("bham.state")


class AppState:
    """Thread-safe, async-friendly in-memory state store."""

    def __init__(self) -> None:
        self._state_lock = threading.Lock()

        # Hardware / session configuration
        self.session_config: Optional[SessionConfig] = None

        # Telemetria bus seriale
        self.bus_health: Optional[BusHealth] = None

        # Discovery results
        self.modbus_devices: dict[str, ModbusDevice] = {}   # key: "<port>-<id>"
        self.bacnet_devices: dict[int, BACnetDevice] = {}   # key: device_id
        self.knx_devices: dict[str, KNXDevice] = {}         # key: "<ip>:<addr>"
        self.ip_hosts: dict[str, IPHost] = {}               # key: ip

        # Active / historical scan sessions
        self.sessions: dict[str, ScanSession] = {}
        self.active_session_id: Optional[str] = None

        # Broadcast hooks (set by WebSocket manager)
        self._broadcast_hooks: list[Callable[[dict], None]] = []

    # ── Session Config ────────────────────────────────────────────────────────

    def set_session_config(self, cfg: SessionConfig) -> None:
        """Applica la configurazione HW e notifica i client WebSocket."""
        self.session_config = cfg
        self._notify({"event": "config_updated", "config": cfg.model_dump(mode="json")})

    # ── Sessions ─────────────────────────────────────────────────────────────

    def new_session(self, protocol: Protocol, parameters: dict) -> ScanSession:
        session = ScanSession(
            id=str(uuid.uuid4()),
            protocol=protocol,
            parameters=parameters,
            status=ScanStatus.IDLE,
        )
        self.sessions[session.id] = session
        self.active_session_id = session.id
        return session

    def update_session(self, session_id: str, **kwargs) -> None:
        if session_id in self.sessions:
            session = self.sessions[session_id]
            for k, v in kwargs.items():
                setattr(session, k, v)
            self._notify({"event": "session_update", "session": session.model_dump(mode="json")})

    def finish_session(self, session_id: str, status: ScanStatus = ScanStatus.COMPLETED) -> None:
        self.update_session(
            session_id,
            status=status,
            finished_at=datetime.now(timezone.utc),
            progress_pct=100.0,
        )
        self.active_session_id = None

    # ── Device upserts ───────────────────────────────────────────────────────

    def upsert_modbus(self, device: ModbusDevice) -> None:
        port = device.serial_params.port if device.serial_params else (device.ip or "tcp")
        key = f"{port}-{device.slave_id}"
        with self._state_lock:
            self.modbus_devices[key] = device
        self._notify({"event": "device_found", "protocol": "modbus", "device": device.model_dump(mode="json")})

    def upsert_bacnet(self, device: BACnetDevice) -> None:
        with self._state_lock:
            self.bacnet_devices[device.device_id] = device
        self._notify({"event": "device_found", "protocol": "bacnet", "device": device.model_dump(mode="json")})

    def upsert_knx(self, device: KNXDevice) -> None:
        key = f"{device.ip_address}:{device.individual_address}"
        with self._state_lock:
            self.knx_devices[key] = device
        self._notify({"event": "device_found", "protocol": "knx", "device": device.model_dump(mode="json")})

    def upsert_ip_host(self, host: IPHost) -> None:
        with self._state_lock:
            existing = self.ip_hosts.get(host.ip)
            if existing:
                host.first_seen = existing.first_seen
            self.ip_hosts[host.ip] = host
        self._notify({"event": "host_found", "host": host.model_dump(mode="json")})

    def update_bus_health(self, health: BusHealth) -> None:
        with self._state_lock:
            self.bus_health = health
        self._notify({"event": "serial_bus_health", "health": health.model_dump(mode="json")})

    def record_serial_frame(self, frame: SerialFrame) -> None:
        self._notify({"event": "serial_frame", "frame": frame.model_dump(mode="json")})

    # ── Broadcast ────────────────────────────────────────────────────────────

    def register_broadcast_hook(self, hook: Callable[[dict], None]) -> None:
        self._broadcast_hooks.append(hook)

    def _notify(self, payload: dict) -> None:
        for hook in self._broadcast_hooks:
            try:
                hook(payload)
            except Exception as exc:
                log.warning("Broadcast hook failed: %s", exc, exc_info=False)

    # ── Snapshot / Reset ─────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        with self._state_lock:
            return {
                "session_config":  self.session_config.model_dump(mode="json") if self.session_config else None,
                "bus_health":      self.bus_health.model_dump(mode="json") if self.bus_health else None,
                "modbus_devices":  [d.model_dump(mode="json") for d in self.modbus_devices.values()],
                "bacnet_devices":  [d.model_dump(mode="json") for d in self.bacnet_devices.values()],
                "knx_devices":     [k.model_dump(mode="json") for k in self.knx_devices.values()],
                "ip_hosts":        [h.model_dump(mode="json") for h in self.ip_hosts.values()],
                "sessions":        [s.model_dump(mode="json") for s in self.sessions.values()],
            }

    def restore_snapshot(self, snap: dict) -> None:
        """Ripristina uno snapshot salvato nello stato attivo e notifica i client."""
        with self._state_lock:
            self.modbus_devices.clear()
            self.bacnet_devices.clear()
            self.knx_devices.clear()
            self.ip_hosts.clear()

            # Configurazione sessione
            if snap.get("session_config"):
                try:
                    self.session_config = SessionConfig.model_validate(snap["session_config"])
                except Exception:
                    pass

            # Dispositivi Modbus
            for d in snap.get("modbus_devices", []):
                try:
                    dev = ModbusDevice.model_validate(d)
                    port = dev.serial_params.port if dev.serial_params else (dev.ip or "tcp")
                    self.modbus_devices[f"{port}-{dev.slave_id}"] = dev
                except Exception:
                    pass

            # Dispositivi BACnet
            for d in snap.get("bacnet_devices", []):
                try:
                    dev = BACnetDevice.model_validate(d)
                    self.bacnet_devices[dev.device_id] = dev
                except Exception:
                    pass

            # Dispositivi KNX
            for k in snap.get("knx_devices", []):
                try:
                    dev = KNXDevice.model_validate(k)
                    self.knx_devices[f"{dev.ip_address}:{dev.individual_address}"] = dev
                except Exception:
                    pass

            # Host IP
            for h in snap.get("ip_hosts", []):
                try:
                    host = IPHost.model_validate(h)
                    self.ip_hosts[host.ip] = host
                except Exception:
                    pass

            # Bus Health
            if snap.get("bus_health"):
                try:
                    self.bus_health = BusHealth.model_validate(snap["bus_health"])
                except Exception:
                    pass

        # Notifiche broadcast ai client
        if self.session_config:
            self._notify({"event": "config_updated", "config": self.session_config.model_dump(mode="json")})
        self._notify({"event": "snapshot", "data": self.snapshot()})

    def get_topology(self) -> dict:
        """
        Genera la rappresentazione a grafo gerarchico dell'impianto collaudato:
        Host -> Interfacce (Seriale, NIC) -> Bus/Segmenti di Protocollo -> Dispositivi/Nodi.
        """
        with self._state_lock:
            site_name = self.session_config.site_name if self.session_config and self.session_config.site_name else "BHAM Field Station"
            serial_port = self.session_config.serial_port if self.session_config and self.session_config.serial_port else DEFAULT_SERIAL_PORT
            baudrate = self.session_config.serial_baudrate if self.session_config else 9600
            parity = self.session_config.serial_parity.value if self.session_config and hasattr(self.session_config.serial_parity, "value") else "N"
            nic_name = self.session_config.scan_iface if self.session_config and self.session_config.scan_iface else "eth0"
            nic_ip = self.session_config.scan_ip if self.session_config and self.session_config.scan_ip else ""

            nodes: list[dict] = []
            links: list[dict] = []

            # 1. Root: Diagnostic Host
            nodes.append({
                "id": "node:host",
                "label": site_name,
                "sublabel": "Host di Collaudo / Master",
                "category": "host",
                "protocol": "system",
                "status": "online",
                "parent_id": None,
                "metrics": {"total_devices": len(self.modbus_devices) + len(self.bacnet_devices) + len(self.knx_devices) + len(self.ip_hosts)},
            })

            # 2. Interfaces: Serial and Ethernet NIC
            # Serial interface
            has_serial_traffic = bool(self.bus_health and self.bus_health.total_frames > 0)
            has_serial_devs = any(
                (d.protocol == Protocol.MODBUS_RTU or (d.serial_params is not None))
                for d in self.modbus_devices.values()
            ) or any(d.protocol == Protocol.BACNET_MSTP for d in self.bacnet_devices.values())
            serial_status = "active" if (has_serial_traffic or has_serial_devs) else "standby"

            nodes.append({
                "id": "node:iface:serial",
                "label": serial_port,
                "sublabel": f"RS485 ({baudrate} 8{parity}1)",
                "category": "interface",
                "protocol": "serial",
                "status": serial_status,
                "parent_id": "node:host",
                "metrics": {
                    "baudrate": baudrate,
                    "parity": parity,
                    "bus_health": self.bus_health.model_dump(mode="json") if self.bus_health else None,
                },
            })
            links.append({"source": "node:host", "target": "node:iface:serial", "protocol": "serial"})

            # Ethernet NIC interface
            has_ip_devs = any(d.protocol == Protocol.MODBUS_TCP for d in self.modbus_devices.values()) or \
                          any(d.protocol == Protocol.BACNET_IP for d in self.bacnet_devices.values()) or \
                          bool(self.knx_devices) or bool(self.ip_hosts)
            nic_status = "active" if has_ip_devs else "standby"

            nodes.append({
                "id": "node:iface:nic",
                "label": nic_name,
                "sublabel": nic_ip if nic_ip else "Ethernet LAN",
                "category": "interface",
                "protocol": "ethernet",
                "status": nic_status,
                "parent_id": "node:host",
                "metrics": {"ip": nic_ip},
            })
            links.append({"source": "node:host", "target": "node:iface:nic", "protocol": "ethernet"})

            # 3. Protocol Buses
            # Modbus RTU bus
            rtu_devs = [
                d for d in self.modbus_devices.values()
                if d.protocol == Protocol.MODBUS_RTU or d.serial_params is not None
            ]
            if rtu_devs or has_serial_traffic:
                nodes.append({
                    "id": "node:bus:modbus_rtu",
                    "label": "Modbus RTU Bus",
                    "sublabel": f"{len(rtu_devs)} slave mappati",
                    "category": "bus",
                    "protocol": "modbus_rtu",
                    "status": "active" if rtu_devs else "standby",
                    "parent_id": "node:iface:serial",
                    "metrics": {"device_count": len(rtu_devs)},
                })
                links.append({"source": "node:iface:serial", "target": "node:bus:modbus_rtu", "protocol": "modbus_rtu"})

            # BACnet MS-TP bus
            mstp_devs = [d for d in self.bacnet_devices.values() if d.protocol == Protocol.BACNET_MSTP]
            if mstp_devs:
                nodes.append({
                    "id": "node:bus:bacnet_mstp",
                    "label": "BACnet MS-TP Token Ring",
                    "sublabel": f"{len(mstp_devs)} nodi ring",
                    "category": "bus",
                    "protocol": "bacnet_mstp",
                    "status": "active",
                    "parent_id": "node:iface:serial",
                    "metrics": {"device_count": len(mstp_devs)},
                })
                links.append({"source": "node:iface:serial", "target": "node:bus:bacnet_mstp", "protocol": "bacnet_mstp"})

            # Modbus TCP bus
            tcp_devs = [d for d in self.modbus_devices.values() if d.protocol == Protocol.MODBUS_TCP]
            if tcp_devs:
                nodes.append({
                    "id": "node:bus:modbus_tcp",
                    "label": "Modbus TCP Network",
                    "sublabel": f"{len(tcp_devs)} server attivi",
                    "category": "bus",
                    "protocol": "modbus_tcp",
                    "status": "active",
                    "parent_id": "node:iface:nic",
                    "metrics": {"device_count": len(tcp_devs)},
                })
                links.append({"source": "node:iface:nic", "target": "node:bus:modbus_tcp", "protocol": "modbus_tcp"})

            # BACnet/IP bus
            bacnet_ip_devs = [d for d in self.bacnet_devices.values() if d.protocol != Protocol.BACNET_MSTP]
            if bacnet_ip_devs:
                nodes.append({
                    "id": "node:bus:bacnet_ip",
                    "label": "BACnet/IP Network",
                    "sublabel": f"{len(bacnet_ip_devs)} dispositivi",
                    "category": "bus",
                    "protocol": "bacnet_ip",
                    "status": "active",
                    "parent_id": "node:iface:nic",
                    "metrics": {"device_count": len(bacnet_ip_devs)},
                })
                links.append({"source": "node:iface:nic", "target": "node:bus:bacnet_ip", "protocol": "bacnet_ip"})

            # KNXnet/IP bus
            if self.knx_devices:
                nodes.append({
                    "id": "node:bus:knx_ip",
                    "label": "KNXnet/IP Network",
                    "sublabel": f"{len(self.knx_devices)} router/gateway",
                    "category": "bus",
                    "protocol": "knx_ip",
                    "status": "active",
                    "parent_id": "node:iface:nic",
                    "metrics": {"device_count": len(self.knx_devices)},
                })
                links.append({"source": "node:iface:nic", "target": "node:bus:knx_ip", "protocol": "knx_ip"})

            # ARP Hosts bus
            if self.ip_hosts:
                nodes.append({
                    "id": "node:bus:arp",
                    "label": "IP Subnet (ARP Hosts)",
                    "sublabel": f"{len(self.ip_hosts)} host L2",
                    "category": "bus",
                    "protocol": "arp",
                    "status": "active",
                    "parent_id": "node:iface:nic",
                    "metrics": {"device_count": len(self.ip_hosts)},
                })
                links.append({"source": "node:iface:nic", "target": "node:bus:arp", "protocol": "arp"})

            # 4. Device Nodes
            # Modbus RTU Devices
            for dev in rtu_devs:
                nid = f"node:dev:modbus:rtu:{dev.slave_id}"
                model_str = dev.registers.get("model", "") or dev.registers.get("vendor", "")
                nodes.append({
                    "id": nid,
                    "label": f"Slave #{dev.slave_id}",
                    "sublabel": model_str if model_str else f"ID {dev.slave_id}",
                    "category": "device",
                    "protocol": "modbus_rtu",
                    "status": "sniffed" if "sniffed" in dev.tags else "active",
                    "parent_id": "node:bus:modbus_rtu",
                    "metrics": {
                        "slave_id": dev.slave_id,
                        "response_time_ms": dev.response_time_ms,
                        "registers_count": len(dev.registers),
                    },
                    "data": dev.model_dump(mode="json"),
                })
                links.append({"source": "node:bus:modbus_rtu", "target": nid, "protocol": "modbus_rtu"})

            # BACnet MS-TP Devices
            for dev in mstp_devs:
                nid = f"node:dev:bacnet:mstp:{dev.device_id}"
                nodes.append({
                    "id": nid,
                    "label": f"MS-TP #{dev.device_id}",
                    "sublabel": f"MAC {dev.address}",
                    "category": "device",
                    "protocol": "bacnet_mstp",
                    "status": "sniffed" if "sniffed" in dev.tags else "active",
                    "parent_id": "node:bus:bacnet_mstp",
                    "metrics": {
                        "device_id": dev.device_id,
                        "address": dev.address,
                        "objects_count": len(dev.object_list),
                    },
                    "data": dev.model_dump(mode="json"),
                })
                links.append({"source": "node:bus:bacnet_mstp", "target": nid, "protocol": "bacnet_mstp"})

            # Modbus TCP Devices
            for dev in tcp_devs:
                nid = f"node:dev:modbus:tcp:{dev.ip}_{dev.tcp_port}_{dev.slave_id}"
                nodes.append({
                    "id": nid,
                    "label": f"TCP #{dev.slave_id}",
                    "sublabel": f"{dev.ip}:{dev.tcp_port}",
                    "category": "device",
                    "protocol": "modbus_tcp",
                    "status": "active",
                    "parent_id": "node:bus:modbus_tcp",
                    "metrics": {
                        "slave_id": dev.slave_id,
                        "ip": dev.ip,
                        "tcp_port": dev.tcp_port,
                        "response_time_ms": dev.response_time_ms,
                    },
                    "data": dev.model_dump(mode="json"),
                })
                links.append({"source": "node:bus:modbus_tcp", "target": nid, "protocol": "modbus_tcp"})

            # BACnet/IP Devices & BBMD Routers
            bbmd_router_nodes: set[str] = set()
            for dev in bacnet_ip_devs:
                nid = f"node:dev:bacnet:ip:{dev.device_id}"
                sub_parts = [p for p in [dev.vendor_name, dev.model_name] if p]
                sub = " - ".join(sub_parts) if sub_parts else dev.address

                # Riconoscimento attraversamento router BBMD
                is_routed = bool(getattr(dev, "bbmd_routed", False) or "bbmd_routed" in dev.tags)
                if is_routed:
                    router_key = getattr(dev, "routed_via", None) or "Router"
                    clean_r_id = router_key.replace(".", "_").replace(":", "_")
                    router_node_id = f"node:router:bbmd:{clean_r_id}"

                    if router_node_id not in bbmd_router_nodes:
                        bbmd_router_nodes.add(router_node_id)
                        nodes.append({
                            "id": router_node_id,
                            "label": f"BBMD ({router_key})",
                            "sublabel": "BACnet Broadcast Management Device",
                            "category": "router",
                            "protocol": "bacnet_ip",
                            "status": "active",
                            "parent_id": "node:bus:bacnet_ip",
                            "metrics": {"bbmd_endpoint": router_key},
                        })
                        links.append({"source": "node:bus:bacnet_ip", "target": router_node_id, "protocol": "bacnet_ip"})

                    parent_id = router_node_id
                    link_source = router_node_id
                else:
                    parent_id = "node:bus:bacnet_ip"
                    link_source = "node:bus:bacnet_ip"

                nodes.append({
                    "id": nid,
                    "label": f"BACnet #{dev.device_id}",
                    "sublabel": sub + (" [BBMD]" if is_routed else ""),
                    "category": "device",
                    "protocol": "bacnet_ip",
                    "status": "active",
                    "parent_id": parent_id,
                    "metrics": {
                        "device_id": dev.device_id,
                        "address": dev.address,
                        "vendor": dev.vendor_name,
                        "model": dev.model_name,
                        "firmware": dev.firmware_revision,
                        "objects_count": len(dev.object_list),
                        "bbmd_routed": is_routed,
                        "routed_via": getattr(dev, "routed_via", None),
                    },
                    "data": dev.model_dump(mode="json"),
                })
                links.append({"source": link_source, "target": nid, "protocol": "bacnet_ip"})


            # KNXnet/IP Devices
            for key, dev in self.knx_devices.items():
                nid = f"node:dev:knx:{dev.individual_address}"
                nodes.append({
                    "id": nid,
                    "label": f"KNX {dev.individual_address}",
                    "sublabel": dev.device_name or dev.ip_address,
                    "category": "device",
                    "protocol": "knx_ip",
                    "status": "active",
                    "parent_id": "node:bus:knx_ip",
                    "metrics": {
                        "individual_address": dev.individual_address,
                        "ip": dev.ip_address,
                        "medium": dev.medium,
                        "serial": dev.serial_number,
                    },
                    "data": dev.model_dump(mode="json"),
                })
                links.append({"source": "node:bus:knx_ip", "target": nid, "protocol": "knx_ip"})

            # ARP Hosts
            for ip, host in self.ip_hosts.items():
                nid = f"node:dev:arp:{ip.replace('.', '_')}"
                vendor_str = getattr(host, "vendor", "") or ""
                sublabel = vendor_str if vendor_str else (host.hostname or host.mac or "Host L2")
                if vendor_str and host.hostname:
                    sublabel = f"{vendor_str} ({host.hostname})"
                nodes.append({
                    "id": nid,
                    "label": host.ip,
                    "sublabel": sublabel,
                    "category": "device",
                    "protocol": "arp",
                    "status": "active",
                    "parent_id": "node:bus:arp",
                    "metrics": {
                        "ip": host.ip,
                        "mac": host.mac,
                        "vendor": vendor_str or "Generico",
                        "hostname": host.hostname,
                        "services": getattr(host, "services", []),
                        "response_time_ms": getattr(host, "response_time_ms", None),
                    },
                    "data": host.model_dump(mode="json"),
                })
                links.append({"source": "node:bus:arp", "target": nid, "protocol": "arp"})

            return {
                "root_id": "node:host",
                "nodes": nodes,
                "links": links,
                "summary": {
                    "total_nodes": len(nodes),
                    "total_links": len(links),
                    "devices": {
                        "modbus_rtu": len(rtu_devs),
                        "modbus_tcp": len(tcp_devs),
                        "bacnet_mstp": len(mstp_devs),
                        "bacnet_ip": len(bacnet_ip_devs),
                        "knx": len(self.knx_devices),
                        "arp": len(self.ip_hosts),
                    }
                }
            }

    def clear(self) -> None:
        with self._state_lock:
            self.bus_health = None
            self.modbus_devices.clear()
            self.bacnet_devices.clear()
            self.knx_devices.clear()
            self.ip_hosts.clear()
        self._notify({"event": "state_cleared"})


# ── Module-level singleton ────────────────────────────────────────────────────
state = AppState()
