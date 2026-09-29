"""
BHAM – Modbus Scanner (RTU & TCP) – Production Engine
======================================================

RTU Pipeline
------------
1. Phase Zero  – Silent listen + CRC-validated frame detection (auto-baud).
2. Early Exit  – Probe "spy IDs" {1, 2, 10} at each param combo; on first HIT
                 → LOCK params, drop timeout to FAST_TIMEOUT, skip remaining combos.
3. Full Sweep  – Scan full ID range at locked params via asyncio thread-pool,
                 N_WORKERS concurrent probes. Progress pushed to AppState.

TCP Pipeline
------------
- Concurrent host sweep via asyncio.gather with semaphore.
- Per-host: try each unit_id until first valid holding-register response.
"""

from __future__ import annotations

import asyncio
import struct
import time
from typing import TYPE_CHECKING, Any, Optional

from core.config import settings
from core.logger import logger
from data.models import ModbusDevice, Parity, Protocol, ScanStatus, SerialParams
from data.state import state
from scanners.base import BaseScanner

if TYPE_CHECKING:
    from api.routes import ModbusRTUScanRequest, ModbusTCPScanRequest

# ── Tunables ──────────────────────────────────────────────────────────────────
SLOW_TIMEOUT   = 0.50   # seconds – probe before LOCK
FAST_TIMEOUT   = 0.12   # seconds – sweep after LOCK
N_RTU_WORKERS  = 1      # serial bus is half-duplex → 1 worker
N_TCP_WORKERS  = 20     # TCP is full-duplex → many concurrent
PHASE_ZERO_PER_BAUD = 1.5  # seconds to listen per baud rate

# ── CRC helper ────────────────────────────────────────────────────────────────

def _calc_crc(data: bytes) -> int:
    """Standard Modbus CRC-16."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def _crc_valid(frame: bytes) -> bool:
    """Return True if the last two bytes of *frame* are a valid CRC."""
    if len(frame) < 4:
        return False
    calc = _calc_crc(frame[:-2])
    recv = struct.unpack_from("<H", frame, len(frame) - 2)[0]
    return calc == recv


def _looks_like_modbus_rtu(data: bytes) -> bool:
    """
    Heuristic: scan a raw byte buffer for any 4+ byte sub-frame with valid CRC.
    Tries every possible start offset and length.
    """
    n = len(data)
    for start in range(n - 3):
        for end in range(start + 4, min(start + 256, n) + 1):
            if _crc_valid(data[start:end]):
                return True
    return False


def parse_modbus_tcp_ports(spec: Any) -> list[int]:
    """
    Parsa una specifica di porte Modbus TCP (int, str, list).
    Supporta:
      - Interi singoli: 502, 503, 5020, 8502
      - Liste separate da virgole/spazi: "502, 503, 5020"
      - Intervalli: "502-505"
    """
    import re
    if spec is None:
        return [502]
    if isinstance(spec, int):
        return [spec]
    if isinstance(spec, list):
        out = []
        for item in spec:
            out.extend(parse_modbus_tcp_ports(item))
        return sorted(list(set(out))) if out else [502]

    spec_str = str(spec).strip()
    if not spec_str:
        return [502]

    ports: list[int] = []
    tokens = re.split(r'[,;\s]+', spec_str)
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        if "-" in tok or ".." in tok:
            delim = ".." if ".." in tok else "-"
            parts = tok.split(delim, 1)
            try:
                p_start = int(parts[0].strip())
                p_end = int(parts[1].strip())
                if p_start <= p_end:
                    ports.extend(range(p_start, min(p_end + 1, p_start + 64)))
                else:
                    ports.append(p_start)
            except Exception:
                pass
        else:
            try:
                ports.append(int(tok))
            except Exception:
                pass
    return sorted(list(set(ports))) if ports else [502]


# ── Modbus Scanner ─────────────────────────────────────────────────────────────

class ModbusScanner(BaseScanner):

    def __init__(self, session_id: str) -> None:
        super().__init__(session_id)
        self._log = logger.getChild("modbus")

    async def scan(self, *args, **kwargs) -> None:
        pass  # satisfies ABC

    # =========================================================================
    # RTU
    # =========================================================================

    async def scan_rtu(self, req: "ModbusRTUScanRequest") -> None:
        log = self._log.getChild("rtu")
        state.update_session(self.session_id, status=ScanStatus.RUNNING, progress_pct=0.0)
        log.info("═══ Modbus RTU scan START – port=%s ═══", req.port)

        # ── Step 1: Phase Zero ───────────────────────────────────────────────
        locked: Optional[dict] = await self._phase_zero(req.port, req.baudrates)

        if locked:
            log.info("Phase Zero LOCK → baud=%d parity=%s stopbits=%d",
                     locked["baudrate"], locked["parity"], locked["stopbits"])
            combos = [locked]
        else:
            log.info("Phase Zero: bus silent – entering brute-force mode")
            combos = [
                {"baudrate": b, "parity": p, "stopbits": s}
                for b in req.baudrates
                for p in req.parities
                for s in req.stopbits
            ]

        # ── Step 2: Early Exit (spy IDs) ─────────────────────────────────────
        if not locked:
            locked = await self._early_exit(req.port, combos, req.spy_ids)

        if not locked:
            log.warning("No response on any parameter combination – 0 devices found.")
            state.finish_session(self.session_id, ScanStatus.COMPLETED)
            return

        log.info("Parameters LOCKED → baud=%d parity=%s stopbits=%d – starting full sweep",
                 locked["baudrate"], locked["parity"], locked["stopbits"])

        # ── Step 3: Full Sweep ───────────────────────────────────────────────
        serial_params = SerialParams(
            port=req.port,
            baudrate=locked["baudrate"],
            parity=Parity(locked["parity"]),
            stopbits=locked["stopbits"],
        )
        await self._full_sweep_rtu(req.port, locked, serial_params, req.id_range)

        found = sum(1 for k in state.modbus_devices if k.startswith(req.port))
        log.info("═══ RTU scan DONE – %d device(s) found ═══", found)
        state.finish_session(self.session_id, ScanStatus.COMPLETED)

    # ── Phase Zero ────────────────────────────────────────────────────────────

    async def _phase_zero(self, port: str, baudrates: list[int]) -> Optional[dict]:
        """
        Listen silently on each baud rate for CRC-valid Modbus RTU traffic.
        Returns locked param dict on first confirmed hit, or None if bus is quiet.
        """
        log = self._log.getChild("phase_zero")
        log.info("Phase Zero: listening on %s (%.1fs per baud rate) …", port, PHASE_ZERO_PER_BAUD)

        loop = asyncio.get_event_loop()
        for baud in baudrates:
            result = await loop.run_in_executor(
                None, self._listen_for_traffic, port, baud, PHASE_ZERO_PER_BAUD
            )
            if result:
                log.info("Phase Zero HIT at %d baud", baud)
                return {"baudrate": baud, "parity": "N", "stopbits": 1}
            if self.is_aborted():
                break
        return None

    def _listen_for_traffic(self, port: str, baudrate: int, duration: float) -> bool:
        """Blocking: open serial port, collect bytes, look for CRC-valid frame."""
        try:
            import serial
        except ImportError:
            self._log.warning("pyserial not available – Phase Zero skipped")
            return False

        try:
            ser = serial.Serial(
                port=port, baudrate=baudrate, bytesize=8,
                parity="N", stopbits=1, timeout=0.1
            )
        except serial.SerialException as exc:
            self._log.debug("Phase Zero cannot open %s at %d: %s", port, baudrate, exc)
            return False

        buf = bytearray()
        deadline = time.monotonic() + duration
        try:
            while time.monotonic() < deadline:
                chunk = ser.read(256)
                if chunk:
                    buf.extend(chunk)
                    # Keep buffer bounded to last 512 bytes
                    if len(buf) > 512:
                        buf = buf[-512:]
                    if len(buf) >= 4 and _looks_like_modbus_rtu(bytes(buf)):
                        return True
        finally:
            ser.close()
        return False

    # ── Early Exit ────────────────────────────────────────────────────────────

    async def _early_exit(
        self, port: str, combos: list[dict], spy_ids: list[int]
    ) -> Optional[dict]:
        """
        Test each parameter combo against spy IDs with a slow timeout.
        Returns the first combo that gets a valid response, or None.
        """
        log = self._log.getChild("early_exit")
        loop = asyncio.get_event_loop()

        for params in combos:
            if self.is_aborted():
                break
            log.debug("Probing spy IDs with %s …", params)
            hit_id = await loop.run_in_executor(
                None, self._probe_spy_ids, port, params, spy_ids
            )
            if hit_id is not None:
                log.info("Early Exit HIT: slave_id=%d → LOCK %s", hit_id, params)
                return params
        return None

    def _probe_spy_ids(self, port: str, params: dict, spy_ids: list[int]) -> Optional[int]:
        """Blocking: try holding-register read on each spy ID. Returns first responding ID."""
        try:
            from pymodbus.client import ModbusSerialClient
        except ImportError:
            self._log.error("pymodbus not installed")
            return None

        client = ModbusSerialClient(
            port=port,
            baudrate=params["baudrate"],
            parity=params.get("parity", "N"),
            stopbits=params.get("stopbits", 1),
            timeout=SLOW_TIMEOUT,
        )
        if not client.connect():
            self._log.debug("Cannot open %s", port)
            return None

        try:
            for sid in spy_ids:
                try:
                    rr = client.read_holding_registers(0, 1, slave=sid)
                    if rr and not rr.isError():
                        return sid
                except Exception:
                    continue
        finally:
            client.close()
        return None

    # ── Full Sweep ────────────────────────────────────────────────────────────

    async def _full_sweep_rtu(
        self,
        port: str,
        params: dict,
        serial_params: SerialParams,
        id_range: list[int],
    ) -> None:
        """
        Sweep *id_range* sequentially (RTU bus is half-duplex).
        Reports progress to state after each probe.
        """
        log = self._log.getChild("sweep")
        loop = asyncio.get_event_loop()
        total = len(id_range)
        found_count = 0

        # Open a persistent client for the sweep (avoid reconnect overhead)
        from pymodbus.client import ModbusSerialClient

        client = ModbusSerialClient(
            port=port,
            baudrate=params["baudrate"],
            parity=params.get("parity", "N"),
            stopbits=params.get("stopbits", 1),
            timeout=FAST_TIMEOUT,
        )
        connected = await loop.run_in_executor(None, client.connect)
        if not connected:
            log.error("Cannot open serial port for full sweep: %s", port)
            return

        try:
            for idx, sid in enumerate(id_range):
                if self.is_aborted():
                    log.info("Sweep aborted at slave_id=%d", sid)
                    break

                device = await loop.run_in_executor(
                    None, self._probe_slave_shared, client, sid, serial_params
                )

                if device:
                    state.upsert_modbus(device)
                    found_count += 1
                    log.info("  ✓ Slave ID %3d  [%.1f ms]", sid, device.response_time_ms or 0)

                pct = (idx + 1) / total * 100
                state.update_session(
                    self.session_id,
                    progress_pct=round(pct, 1),
                    found_devices=found_count,
                )
        finally:
            await loop.run_in_executor(None, client.close)

    def _probe_slave_shared(
        self,
        client,          # shared ModbusSerialClient (already connected)
        slave_id: int,
        serial_params: SerialParams,
    ) -> Optional[ModbusDevice]:
        """
        Attempt to read holding register 0 from *slave_id*.
        Falls back to Read Device Identification (FC 43) on error.
        """
        try:
            t0 = time.monotonic()
            rr = client.read_holding_registers(0, 1, slave=slave_id)
            elapsed_ms = (time.monotonic() - t0) * 1000

            if rr and not rr.isError():
                return ModbusDevice(
                    slave_id=slave_id,
                    protocol=Protocol.MODBUS_RTU,
                    serial_params=serial_params,
                    response_time_ms=round(elapsed_ms, 2),
                )
        except Exception:
            pass
        return None

    # =========================================================================
    # TCP
    # =========================================================================

    async def scan_tcp(self, req: "ModbusTCPScanRequest") -> None:
        log = self._log.getChild("tcp")
        state.update_session(self.session_id, status=ScanStatus.RUNNING, progress_pct=0.0)

        # Espandi CIDR subnet se presenti
        from ipaddress import ip_network, ip_address
        expanded_hosts: list[str] = []
        for host_spec in req.hosts:
            try:
                net = ip_network(host_spec, strict=False)
                if net.num_addresses == 1:
                    expanded_hosts.append(host_spec)
                else:
                    expanded_hosts.extend(str(ip) for ip in net.hosts())
            except ValueError:
                expanded_hosts.append(host_spec)

        target_ports = parse_modbus_tcp_ports(req.tcp_ports or getattr(req, "tcp_port", 502))
        port_desc = ", ".join(str(p) for p in target_ports)
        targets = [(h, p) for h in expanded_hosts for p in target_ports]
        total = len(targets)
        log.info("═══ Modbus TCP scan START – %d target(s) across %d host(s) on port(s) %s ═══",
                 total, len(req.hosts), port_desc)

        sem = asyncio.Semaphore(N_TCP_WORKERS)
        found_count = 0
        done_count = 0

        async def _scan_one(host: str, port: int) -> Optional[ModbusDevice]:
            async with sem:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, self._probe_tcp_host, host, port, req.unit_ids
                )

        tasks = [asyncio.create_task(_scan_one(h, p)) for h, p in targets]
        pending = set(tasks)

        while pending:
            if self.is_aborted():
                for t in pending:
                    t.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                break

            done, pending = await asyncio.wait(
                pending, timeout=0.2, return_when=asyncio.FIRST_COMPLETED
            )
            for t in done:
                try:
                    device = t.result()
                except Exception:
                    device = None
                done_count += 1

                if device:
                    state.upsert_modbus(device)
                    found_count += 1
                    log.info("  ✓ %s:%d  unit=%d  [%.1f ms]",
                             device.ip, device.tcp_port,
                             device.slave_id, device.response_time_ms or 0)

                state.update_session(
                    self.session_id,
                    progress_pct=round(done_count / total * 100, 1) if total > 0 else 100.0,
                    found_devices=found_count,
                )

        log.info("═══ TCP scan DONE – %d device(s) found ═══", found_count)
        state.finish_session(self.session_id, ScanStatus.COMPLETED)

    def _probe_tcp_host(
        self, host: str, port: int, unit_ids: list[int]
    ) -> Optional[ModbusDevice]:
        try:
            from pymodbus.client import ModbusTcpClient
        except ImportError:
            return None

        client = ModbusTcpClient(host, port=port, timeout=settings.modbus_tcp_timeout)
        if not client.connect():
            return None

        try:
            for uid in unit_ids:
                t0 = time.monotonic()
                try:
                    rr = client.read_holding_registers(0, 1, slave=uid)
                    if rr and not rr.isError():
                        elapsed_ms = (time.monotonic() - t0) * 1000
                        return ModbusDevice(
                            slave_id=uid,
                            protocol=Protocol.MODBUS_TCP,
                            ip=host,
                            tcp_port=port,
                            response_time_ms=round(elapsed_ms, 2),
                        )
                except Exception:
                    continue
        finally:
            client.close()
        return None


# =========================================================================
# FC43 – Device Identification (MEI Read Device Identification)
# =========================================================================

async def read_device_identification(
    port: str,
    params: dict,
    slave_id: int,
) -> dict:
    """
    Standalone coroutine: send Modbus FC43/ME 0x0E (Read Device Identification)
    to a specific slave and return a dict with vendor/product/version strings.

    Supported read_device_id codes (MEI type 0x0E):
      01 = Basic    (VendorName, ProductCode, MajorMinorRevision)
      02 = Regular  (+ VendorURL, ProductName, ModelName)
      03 = Extended (+ all objects in stream)

    Falls back gracefully if the slave doesn't support FC43.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _fc43_blocking, port, params, slave_id
    )


def _fc43_blocking(port: str, params: dict, slave_id: int) -> dict:
    """Blocking FC43 probe – run in thread pool."""
    result: dict = {"slave_id": slave_id, "supported": False}
    try:
        from pymodbus.client import ModbusSerialClient
        from pymodbus.mei_message import ReadDeviceInformationRequest

        client = ModbusSerialClient(
            port=port,
            baudrate=params["baudrate"],
            parity=params.get("parity", "N"),
            stopbits=params.get("stopbits", 1),
            timeout=SLOW_TIMEOUT,
        )
        if not client.connect():
            return result
        try:
            # Try Basic level first (read_code=1)
            req = ReadDeviceInformationRequest(read_code=1, object_id=0, slave=slave_id)
            rr = client.execute(req)
            if rr and not rr.isError():
                result["supported"] = True
                info = rr.information  # dict {obj_id: bytes}
                _OBJ = {
                    0x00: "vendor_name",
                    0x01: "product_code",
                    0x02: "revision",
                    0x03: "vendor_url",
                    0x04: "product_name",
                    0x05: "model_name",
                    0x06: "user_application_name",
                }
                for obj_id, key in _OBJ.items():
                    if obj_id in info:
                        try:
                            result[key] = info[obj_id].decode("ascii", errors="replace").strip()
                        except Exception:
                            pass
        finally:
            client.close()
    except Exception as exc:
        result["error"] = str(exc)
    return result
