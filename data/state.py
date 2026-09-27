"""
BHAM – In-Memory Application State
Single shared singleton; all mutations must go through its methods to keep
the WebSocket broadcast pipeline consistent.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

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


class AppState:
    """Thread-safe, async-friendly in-memory state store."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

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
        self.modbus_devices[key] = device
        self._notify({"event": "device_found", "protocol": "modbus", "device": device.model_dump(mode="json")})

    def upsert_bacnet(self, device: BACnetDevice) -> None:
        self.bacnet_devices[device.device_id] = device
        self._notify({"event": "device_found", "protocol": "bacnet", "device": device.model_dump(mode="json")})

    def upsert_knx(self, device: KNXDevice) -> None:
        key = f"{device.ip_address}:{device.individual_address}"
        self.knx_devices[key] = device
        self._notify({"event": "device_found", "protocol": "knx", "device": device.model_dump(mode="json")})

    def upsert_ip_host(self, host: IPHost) -> None:
        existing = self.ip_hosts.get(host.ip)
        if existing:
            host.first_seen = existing.first_seen
        self.ip_hosts[host.ip] = host
        self._notify({"event": "host_found", "host": host.model_dump(mode="json")})

    def update_bus_health(self, health: BusHealth) -> None:
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
            except Exception:
                pass

    # ── Snapshot / Reset ─────────────────────────────────────────────────────

    def snapshot(self) -> dict:
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

        # Notifiche broadcast ai client
        if self.session_config:
            self._notify({"event": "config_updated", "config": self.session_config.model_dump(mode="json")})
        self._notify({"event": "snapshot", "data": self.snapshot()})

    def clear(self) -> None:
        self.bus_health = None
        self.modbus_devices.clear()
        self.bacnet_devices.clear()
        self.knx_devices.clear()
        self.ip_hosts.clear()
        self._notify({"event": "state_cleared"})


# ── Module-level singleton ────────────────────────────────────────────────────
state = AppState()
