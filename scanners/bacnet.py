"""
BHAM – BACnet Scanner (IP & MS-TP) – Production Engine
=======================================================

Pipeline BACnet/IP
------------------
1. Who-Is broadcast  → raccoglie tutti gli I-Am sulla LAN
2. Per ogni device: Read Property per i campi diagnostici chiave
   (vendor-identifier, vendor-name, model-name, firmware-revision,
    application-software-version, object-list)
3. Tutti i risultati vengono pushati ad AppState in tempo reale

Nota su bacpypes3
-----------------
bacpypes3 è nativo asyncio. L'Application gestisce la ricezione
degli I-Am tramite indication callback. Usiamo un asyncio.Event
per attendere la fine della finestra di discovery.
"""

from __future__ import annotations

import asyncio
import ipaddress
from typing import TYPE_CHECKING, Optional

from core.config import settings
from core.logger import logger
from data.models import BACnetDevice, Protocol, ScanStatus
from data.state import state
from scanners.base import BaseScanner

if TYPE_CHECKING:
    from api.routes import BACnetIPScanRequest

# ── Tunables ──────────────────────────────────────────────────────────────────
WHOIS_WINDOW     = 3.0    # seconds to collect I-Am after Who-Is
READ_PROP_TIMEOUT = 2.0   # seconds per Read Property request
BATCH_SIZE       = 10     # concurrent Read Property requests


# ── Property IDs (BACnet standard) ───────────────────────────────────────────
_PROP_VENDOR_ID    = "vendor-identifier"
_PROP_VENDOR_NAME  = "vendor-name"
_PROP_MODEL_NAME   = "model-name"
_PROP_FW_REV       = "firmware-revision"
_PROP_SW_VER       = "application-software-version"
_PROP_OBJ_LIST     = "object-list"
_PROP_OBJ_NAME     = "object-name"

_DIAGNOSTIC_PROPS = [
    _PROP_VENDOR_ID,
    _PROP_VENDOR_NAME,
    _PROP_MODEL_NAME,
    _PROP_FW_REV,
    _PROP_SW_VER,
]


def parse_bacnet_ports(spec: Any) -> list[int]:
    """
    Parsa una specifica di porte BACnet (int, str o list).
    Supporta:
      - Porte intere dirette: 47808, 47809
      - Notazione BACnet simbolica: "BAC0" -> 47808, "BAC1" -> 47809, ... "BACF" -> 47823
      - Intervalli: "BAC0..BAC3", "BAC0-BAC3", "47808-47812"
      - Liste separate da virgola: "BAC0, BAC1, 47815"
    """
    import re
    if spec is None:
        return [47808]
    if isinstance(spec, int):
        return [spec]
    if isinstance(spec, list):
        out = []
        for item in spec:
            out.extend(parse_bacnet_ports(item))
        return sorted(list(set(out))) if out else [47808]

    spec_str = str(spec).strip().upper()
    if not spec_str:
        return [47808]

    def _token_to_port(tok: str) -> int:
        t = re.sub(r'\(.*?\)', '', tok).strip()
        if t.startswith("0X"):
            return int(t, 16)
        if t.startswith("BAC"):
            hex_part = t[3:]
            return int("BAC" + hex_part, 16)
        return int(t)

    ports: list[int] = []
    tokens = re.split(r'[,;]+', spec_str)
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        if ".." in tok or "-" in tok:
            delim = ".." if ".." in tok else "-"
            parts = tok.split(delim, 1)
            try:
                p_start = _token_to_port(parts[0])
                p_end = _token_to_port(parts[1])
                if p_start <= p_end:
                    ports.extend(range(p_start, min(p_end + 1, p_start + 64)))
                else:
                    ports.append(p_start)
            except Exception:
                pass
        else:
            try:
                ports.append(_token_to_port(tok))
            except Exception:
                pass
    return sorted(list(set(ports))) if ports else [47808]


def port_label(port: int) -> str:
    """Formatta la porta aggiungendo il codice BACx se compreso tra 47808 e 47823."""
    if 47808 <= port <= 47823:
        return f"BAC{port - 47808:X} ({port})"
    return f"{port}"


class BACnetScanner(BaseScanner):

    def __init__(self, session_id: str) -> None:
        super().__init__(session_id)
        self._log = logger.getChild("bacnet")

    async def scan(self, *args, **kwargs) -> None:
        pass

    # =========================================================================
    # BACnet/IP – main entry
    # =========================================================================

    async def scan_ip(self, req: "BACnetIPScanRequest") -> None:
        log = self._log.getChild("ip")
        state.update_session(self.session_id, status=ScanStatus.RUNNING, progress_pct=0.0)

        target_ports = parse_bacnet_ports(req.ports or req.port)
        port_desc = ", ".join(port_label(p) for p in target_ports)
        log.info("═══ BACnet/IP scan START (iface=%r, ports=%s) ═══", req.iface or "auto", port_desc)

        found_devices: dict[int, BACnetDevice] = {}

        try:
            await self._run_bacnet_discovery(req, target_ports, found_devices)
        except ImportError as exc:
            log.error("bacpypes3 non installato: %s", exc)
            state.finish_session(self.session_id, ScanStatus.ERROR)
            return
        except Exception as exc:
            log.error("BACnet scan error: %s", exc, exc_info=True)
            state.finish_session(self.session_id, ScanStatus.ERROR)
            return

        # ── Read properties per ogni device trovato ──────────────────────────
        if found_devices:
            log.info("Reading properties for %d device(s) …", len(found_devices))
            await self._enrich_devices(found_devices)

        count = len(found_devices)
        log.info("═══ BACnet/IP scan DONE – %d device(s) found ═══", count)
        state.update_session(self.session_id, found_devices=count, progress_pct=100.0)
        state.finish_session(self.session_id, ScanStatus.COMPLETED)

    # =========================================================================
    # Who-Is / I-Am Discovery
    # =========================================================================

    async def _run_bacnet_discovery(
        self, req: "BACnetIPScanRequest", target_ports: list[int], found: dict[int, BACnetDevice]
    ) -> None:
        """
        Broadcast Who-Is su ciascuna porta specificata (BAC0..BACF, custom o lista)
        e raccoglie le risposte I-Am.
        """
        from bacpypes3.ipv4.app import NormalApplication
        from bacpypes3.local.device import DeviceObject
        from bacpypes3.pdu import IPv4Address
        from bacpypes3.primitivedata import ObjectIdentifier

        log = self._log.getChild("whois")

        cfg = state.session_config
        host_ip = cfg.scan_ip if cfg and cfg.scan_ip else (req.iface if req.iface and "." in req.iface else "")
        if not host_ip or host_ip == "0.0.0.0":
            import socket
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    host_ip = s.getsockname()[0]
            except Exception:
                host_ip = "127.0.0.1"

        # Finestra di ascolto per porta (più breve se scansioniamo molte porte)
        window = WHOIS_WINDOW if len(target_ports) == 1 else max(1.5, WHOIS_WINDOW / len(target_ports))

        for idx, port in enumerate(target_ports):
            if self.is_aborted():
                log.warning("Scansione BACnet interrotta dall'operatore.")
                break

            pct = (idx / len(target_ports)) * 50.0
            state.update_session(self.session_id, progress_pct=round(pct, 1))
            log.info("Sonda BACnet/IP Who-Is su porta %s...", port_label(port))

            local_device = DeviceObject(
                objectIdentifier=ObjectIdentifier(f"device,{9990 + (port % 10)}"),
                objectName=f"BHAM-probe-{port}",
                vendorIdentifier=999,
                vendorName="BHAM",
            )

            cidr = "/8" if host_ip.startswith("127.") else "/24"
            bind_str = f"{host_ip}{cidr}:{port}" if "/" not in host_ip else f"{host_ip}:{port}"
            try:
                bind_addr = IPv4Address(bind_str)
                app = NormalApplication(local_device, bind_addr)
                if hasattr(app.normal.server, "_transport_tasks") and app.normal.server._transport_tasks:
                    await asyncio.gather(*app.normal.server._transport_tasks)
            except Exception as bind_err:
                log.warning("Impossibile effettuare bind su %s: %s (porta in uso?)", bind_str, bind_err)
                continue

            fut = app.who_is(timeout=max(1, int(round(window))))
            try:
                while not fut.done():
                    if self.is_aborted():
                        fut.cancel()
                        break
                    await asyncio.sleep(0.05)

                if fut.done() and not fut.cancelled():
                    i_ams = fut.result()
                    for iam_apdu in (i_ams or []):
                        try:
                            dev_id = int(iam_apdu.iAmDeviceIdentifier[1])
                            address = str(iam_apdu.pduSource)
                            vendor_id = int(getattr(iam_apdu, "vendorID", 0)) or None
                            if dev_id in found:
                                continue
                            device = BACnetDevice(
                                device_id=dev_id,
                                protocol=Protocol.BACNET_IP,
                                address=address,
                                vendor_id=vendor_id,
                            )
                            found[dev_id] = device
                            state.upsert_bacnet(device)
                            log.info("  ✓ I-Am: device_id=%d address=%s (porta %s)", dev_id, address, port_label(port))
                        except Exception as exc:
                            log.debug("I-Am parse error: %s", exc)
            except Exception as whois_err:
                log.warning("Errore durante Who-Is su porta %s: %s", port_label(port), whois_err)
            finally:
                try:
                    app.close()
                    await asyncio.sleep(0.03)
                except Exception:
                    pass

    # =========================================================================
    # Read Property (enrich discovered devices)
    # =========================================================================

    async def _enrich_devices(self, devices: dict[int, BACnetDevice]) -> None:
        """Read diagnostic properties for each discovered device (batched)."""
        sem = asyncio.Semaphore(BATCH_SIZE)
        total = len(devices)

        async def _enrich_one(idx: int, device: BACnetDevice) -> None:
            async with sem:
                if self.is_aborted():
                    return
                await self._read_device_properties(device)
                state.upsert_bacnet(device)  # push enriched data
                pct = (idx + 1) / total * 100
                state.update_session(
                    self.session_id,
                    progress_pct=round(pct, 1),
                    found_devices=total,
                )

        tasks = [
            asyncio.create_task(_enrich_one(i, d))
            for i, d in enumerate(devices.values())
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _read_device_properties(self, device: BACnetDevice) -> None:
        """
        Read diagnostic properties from a single BACnet device.
        Errors on individual properties are silently swallowed.
        """
        log = self._log.getChild("read_prop")
        try:
            from bacpypes3.app import Application
            from bacpypes3.local.device import DeviceObject
            from bacpypes3.pdu import Address
            from bacpypes3.apdu import ReadPropertyRequest, ReadPropertyACK
            from bacpypes3.primitivedata import ObjectIdentifier, CharacterString
            from bacpypes3.basetypes import PropertyIdentifier

            # Spin up a transient application for this read
            local_device = DeviceObject(
                objectIdentifier=ObjectIdentifier("device,9997"),
                objectName="BHAM-reader",
                vendorIdentifier=999,
            )
            app = Application(local_device)
            target = Address(device.address)
            obj_id = ObjectIdentifier(f"device,{device.device_id}")

            prop_map = {
                "vendor-identifier":              "vendor_id",
                "vendor-name":                    "vendor_name",
                "model-name":                     "model_name",
                "firmware-revision":              "firmware_revision",
                "application-software-version":   "application_software_version",
            }

            for prop_name, attr in prop_map.items():
                try:
                    request = ReadPropertyRequest(
                        objectIdentifier=obj_id,
                        propertyIdentifier=PropertyIdentifier(prop_name),
                    )
                    request.pduDestination = target
                    response = await asyncio.wait_for(
                        app.request(request, target),
                        timeout=READ_PROP_TIMEOUT,
                    )
                    if isinstance(response, ReadPropertyACK):
                        val = response.propertyValue.cast_out(CharacterString)
                        setattr(device, attr, str(val))
                        log.debug("  device=%d %s=%s", device.device_id, prop_name, val)
                except asyncio.TimeoutError:
                    log.debug("  Timeout reading %s from device %d", prop_name, device.device_id)
                except Exception as exc:
                    log.debug("  Error reading %s from device %d: %s", prop_name, device.device_id, exc)

            await app.close()

        except Exception as exc:
            log.warning("Property read failed for device %d: %s", device.device_id, exc)
