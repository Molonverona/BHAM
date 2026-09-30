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
from typing import TYPE_CHECKING, Any, Optional

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

        # Se è specificato un router BBMD, effettua registrazione Foreign Device e Who-Is traversale
        if req.bbmd_ip and req.bbmd_ip.strip():
            bbmd_ip = req.bbmd_ip.strip()
            bbmd_ports = parse_bacnet_ports(req.bbmd_port or 47808)
            bbmd_port = bbmd_ports[0] if bbmd_ports else 47808
            ttl = int(req.bbmd_ttl) if req.bbmd_ttl else 60

            log.info("═══ BACnet/IP BBMD Foreign Device Discovery -> %s:%d (TTL=%ds) ═══", bbmd_ip, bbmd_port, ttl)
            state.update_session(self.session_id, progress_pct=15.0)

            from bacpypes3.ipv4.app import ForeignApplication

            local_device = DeviceObject(
                objectIdentifier=ObjectIdentifier("device,9991"),
                objectName="BHAM-bbmd-probe",
                vendorIdentifier=999,
                vendorName="BHAM",
            )
            bind_str = f"{host_ip}:0" if host_ip and host_ip != "0.0.0.0" else "0.0.0.0:0"
            try:
                bind_addr = IPv4Address(bind_str)
                app = ForeignApplication(local_device, bind_addr)
                if hasattr(app.server, "_transport_tasks") and app.server._transport_tasks:
                    await asyncio.gather(*app.server._transport_tasks)

                bbmd_addr = IPv4Address(f"{bbmd_ip}:{bbmd_port}")
                app.register(bbmd_addr, ttl)
                log.info("  ✓ Foreign Device registrato presso BBMD %s:%d (attesa I-Am...)", bbmd_ip, bbmd_port)
            except Exception as reg_err:
                log.warning("Impossibile registrare Foreign Device su %s:%d: %s", bbmd_ip, bbmd_port, reg_err)
                return

            try:
                fut = app.who_is(timeout=max(1, int(round(WHOIS_WINDOW))))
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
                                bbmd_routed=True,
                                routed_via=f"{bbmd_ip}:{bbmd_port}",
                                tags=["bbmd_routed"],
                            )
                            found[dev_id] = device
                            state.upsert_bacnet(device)
                            log.info("  ✓ I-Am via BBMD: device_id=%d address=%s", dev_id, address)
                        except Exception as exc:
                            log.debug("I-Am parse error: %s", exc)
            except Exception as whois_err:
                log.warning("Errore durante Who-Is via BBMD %s:%d: %s", bbmd_ip, bbmd_port, whois_err)
            finally:
                try:
                    app.unregister()
                except Exception:
                    pass
                try:
                    app.close()
                    await asyncio.sleep(0.03)
                except Exception:
                    pass
            return

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
        if not devices:
            return

        # Crea una singola Application per tutte le letture (riuso, non 10 bind concorrenti)
        try:
            from bacpypes3.app import Application
            from bacpypes3.local.device import DeviceObject
            from bacpypes3.primitivedata import ObjectIdentifier

            local_device = DeviceObject(
                objectIdentifier=ObjectIdentifier("device,9998"),
                objectName="BHAM-enricher",
                vendorIdentifier=999,
            )
            app = Application(local_device)
        except Exception as exc:
            self._log.warning("Cannot create BACnet app for property enrichment: %s", exc)
            return

        sem = asyncio.Semaphore(BATCH_SIZE)
        total = len(devices)

        async def _enrich_one(idx: int, device: BACnetDevice) -> None:
            async with sem:
                if self.is_aborted():
                    return
                await self._read_device_properties(device, app)
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

        try:
            await app.close()
        except Exception:
            pass

    async def _read_device_properties(self, device: BACnetDevice, app) -> None:
        """
        Read diagnostic properties from a single BACnet device.
        Uses a shared Application passed from _enrich_devices.
        Errors on individual properties are silently swallowed.
        """
        log = self._log.getChild("read_prop")
        try:
            from bacpypes3.pdu import Address
            from bacpypes3.apdu import ReadPropertyRequest, ReadPropertyACK
            from bacpypes3.primitivedata import ObjectIdentifier, CharacterString
            from bacpypes3.basetypes import PropertyIdentifier

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

        except Exception as exc:
            log.warning("Property read failed for device %d: %s", device.device_id, exc)


# =========================================================================
# Object Explorer – Interactive Object List Discovery & Inspection
# =========================================================================

async def explore_bacnet_objects(
    device_id: int,
    address: Optional[str] = None,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """
    Enumerate and read all BACnet objects (Analog Input/Output, Binary, etc.)
    and their presentValue, objectName, units, and outOfService status.
    """
    dev = state.bacnet_devices.get(device_id)
    target_addr_str = address or (dev.address if dev else None)
    if not target_addr_str:
        return {
            "device_id": device_id,
            "error": f"Nessun indirizzo noto per il dispositivo BACnet #{device_id}",
            "objects": dev.object_list if dev else [],
        }

    try:
        from bacpypes3.ipv4.app import NormalApplication
        from bacpypes3.pdu import IPv4Address, Address
        from bacpypes3.local.device import DeviceObject
        from bacpypes3.primitivedata import ObjectIdentifier, CharacterString
        from bacpypes3.basetypes import PropertyIdentifier

        local_device = DeviceObject(
            objectIdentifier=ObjectIdentifier(f"device,9995"),
            objectName="BHAM-obj-explorer",
            vendorIdentifier=999,
        )
        bind_addr = IPv4Address("127.0.0.1/24:0")
        app = NormalApplication(local_device, bind_addr)
        if hasattr(app.normal.server, "_transport_tasks") and app.normal.server._transport_tasks:
            await asyncio.gather(*app.normal.server._transport_tasks)
    except Exception as exc:
        return {
            "device_id": device_id,
            "error": f"Inizializzazione stack BACnet fallita: {exc}",
            "objects": dev.object_list if dev else [],
        }

    discovered_objects: list[dict[str, Any]] = []
    try:
        target = Address(target_addr_str)
        dev_obj_id = ObjectIdentifier(f"device,{device_id}")

        # 1. Prova a leggere 'object-list'
        obj_identifiers: list[Any] = []
        try:
            val = await asyncio.wait_for(
                app.read_property(target, dev_obj_id, "object-list"),
                timeout=timeout,
            )
            if isinstance(val, (list, tuple)):
                obj_identifiers = list(val)
        except Exception as exc:
            logger.debug("Lettura diretta object-list non riuscita per device %d: %s. Tentativo probe selettivo.", device_id, exc)

        # 2. Se object-list non è disponibile o vuota, prova con probe selettivo dei tipi comuni
        if not obj_identifiers:
            common_types = [
                ("analog-input", range(0, 5)),
                ("analog-value", range(0, 5)),
                ("binary-input", range(0, 5)),
                ("binary-value", range(0, 5)),
            ]
            for obj_type, instances in common_types:
                for inst in instances:
                    obj_identifiers.append((obj_type, inst))

        # 3. Lettura dettagliata per ciascun oggetto (limite di sicurezza a 150 oggetti per evitare freeze)
        consecutive_timeouts = 0
        for item in obj_identifiers[:150]:
            if consecutive_timeouts >= 2:
                # Se due probe consecutivi vanno in timeout/errore, l'host non è raggiungibile: esci subito
                break
            try:
                if isinstance(item, tuple) or hasattr(item, "__getitem__"):
                    obj_type_str = str(item[0]).lower().replace("_", "-")
                    obj_inst = int(item[1])
                elif isinstance(item, str):
                    parts = item.split(",") if "," in item else item.split(":")
                    obj_type_str = parts[0].strip().lower().replace("_", "-")
                    obj_inst = int(parts[1].strip())
                elif hasattr(item, "value"):
                    # bacpypes3 ObjectIdentifier instance
                    obj_type_str = str(item.value[0]).lower().replace("_", "-")
                    obj_inst = int(item.value[1])
                else:
                    continue

                if obj_type_str == "device":
                    continue

                cur_obj_id = ObjectIdentifier(f"{obj_type_str},{obj_inst}")

                # Read object-name
                name = ""
                try:
                    name_val = await asyncio.wait_for(
                        app.read_property(target, cur_obj_id, "object-name"),
                        timeout=0.4,
                    )
                    name = str(name_val) if name_val is not None else ""
                except Exception:
                    pass

                # Read present-value
                pres_val = None
                try:
                    pv_val = await asyncio.wait_for(
                        app.read_property(target, cur_obj_id, "present-value"),
                        timeout=0.4,
                    )
                    if pv_val is not None:
                        pres_val = str(pv_val)
                except Exception:
                    pass

                # If both name and present_value failed on probed list, object doesn't exist
                if not name and pres_val is None:
                    consecutive_timeouts += 1
                    continue

                consecutive_timeouts = 0

                # Read units (for analog objects)
                units = ""
                if "analog" in obj_type_str or "accumulator" in obj_type_str:
                    try:
                        u_val = await asyncio.wait_for(
                            app.read_property(target, cur_obj_id, "units"),
                            timeout=0.4,
                        )
                        if u_val is not None:
                            units = str(u_val)
                    except Exception:
                        pass

                # Format human readable units
                unit_map = {
                    "degrees-celsius": "°C",
                    "degrees-fahrenheit": "°F",
                    "percent": "%",
                    "parts-per-million": "ppm",
                    "pascals": "Pa",
                    "kilopascals": "kPa",
                    "bars": "bar",
                    "volts": "V",
                    "amperes": "A",
                    "kilowatt-hours": "kWh",
                    "kilowatts": "kW",
                    "liters-per-second": "l/s",
                    "cubic-meters-per-hour": "m³/h",
                    "hertz": "Hz",
                    "revolutions-per-minute": "rpm",
                }
                display_unit = unit_map.get(units.lower(), units)

                discovered_objects.append({
                    "identifier": f"{obj_type_str}:{obj_inst}",
                    "type": obj_type_str,
                    "instance": obj_inst,
                    "name": name or f"{obj_type_str}_{obj_inst}",
                    "present_value": pres_val if pres_val is not None else "—",
                    "units": display_unit,
                })
            except Exception as item_err:
                logger.debug("Error exploring object %s: %s", item, item_err)
                continue

    finally:
        try:
            await app.close()
        except Exception:
            pass

    # Aggiorna lo stato se il dispositivo è censito
    if dev:
        dev.object_list = discovered_objects
        state.upsert_bacnet(dev)

    return {
        "device_id": device_id,
        "address": target_addr_str,
        "count": len(discovered_objects),
        "objects": discovered_objects,
    }


# =========================================================================
# BBMD Table Inspection (Annex J BVLL Read-BDT & Read-FDT)
# =========================================================================

class _BVLLResponseProtocol(asyncio.DatagramProtocol):
    """Protocollo Datagram asyncio per transazioni BVLL request-response."""

    def __init__(self) -> None:
        self.fut = asyncio.get_running_loop().create_future()
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if not self.fut.done():
            self.fut.set_result((data, addr))

    def error_received(self, exc: Exception) -> None:
        if not self.fut.done():
            self.fut.set_exception(exc)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if not self.fut.done():
            self.fut.set_exception(exc or asyncio.CancelledError())


def decode_bdt_payload(payload: bytes) -> list[dict[str, Any]]:
    """
    Decodifica il payload di un Read-BDT-Ack (ASHRAE 135 Annex J.4.2).
    Ogni entry è di 10 byte:
      - 4 byte: IPv4 Address
      - 2 byte: UDP Port
      - 4 byte: Broadcast Distribution Mask
    """
    import socket
    import struct
    records = []
    for i in range(0, len(payload), 10):
        chunk = payload[i:i + 10]
        if len(chunk) == 10:
            ip_b, port, mask_b = struct.unpack("!4sH4s", chunk)
            records.append({
                "ip": socket.inet_ntoa(ip_b),
                "port": port,
                "broadcast_mask": socket.inet_ntoa(mask_b),
            })
    return records


def decode_fdt_payload(payload: bytes) -> list[dict[str, Any]]:
    """
    Decodifica il payload di un Read-FDT-Ack (ASHRAE 135 Annex J.4.4).
    Ogni entry è di 10 byte:
      - 4 byte: IPv4 Address
      - 2 byte: UDP Port
      - 2 byte: Time-to-Live (TTL)
      - 2 byte: Remaining Time-to-Live
    """
    import socket
    import struct
    records = []
    for i in range(0, len(payload), 10):
        chunk = payload[i:i + 10]
        if len(chunk) == 10:
            ip_b, port, ttl, remaining = struct.unpack("!4sHHH", chunk)
            records.append({
                "ip": socket.inet_ntoa(ip_b),
                "port": port,
                "ttl": ttl,
                "remaining_time": remaining,
            })
    return records


async def read_bdt(bbmd_ip: str, bbmd_port: int = 47808, timeout: float = 3.0) -> list[dict[str, Any]]:
    """
    Legge la Broadcast Distribution Table (BDT) da un BBMD BACnet/IP
    inviando un messaggio BVLL Read-Broadcast-Distribution-Table (0x81 0x02 0x00 0x04).
    """
    import struct
    loop = asyncio.get_running_loop()
    transport: Optional[asyncio.DatagramTransport] = None
    try:
        transport_raw, protocol = await loop.create_datagram_endpoint(
            lambda: _BVLLResponseProtocol(),
            local_addr=("0.0.0.0", 0)
        )
        transport = transport_raw  # type: ignore[assignment]
        # Pacchetto BVLL Read-BDT: Type=0x81, Func=0x02, Len=0x0004
        req = bytes([0x81, 0x02, 0x00, 0x04])
        transport.sendto(req, (bbmd_ip, bbmd_port))
        data, _ = await asyncio.wait_for(protocol.fut, timeout=timeout)
        if len(data) >= 4 and data[0] == 0x81:
            func = data[1]
            length = struct.unpack("!H", data[2:4])[0]
            if func == 0x03:  # Read-BDT-Ack
                payload = data[4:length]
                return decode_bdt_payload(payload)
            elif func == 0x00:  # BVLL-Result
                res_code = struct.unpack("!H", data[4:6])[0] if len(data) >= 6 else -1
                logger.warning("BBMD %s:%d ha risposto con BVLL-Result NAK: 0x%04X", bbmd_ip, bbmd_port, res_code)
        return []
    except asyncio.TimeoutError:
        logger.debug("Timeout nella lettura BDT da BBMD %s:%d", bbmd_ip, bbmd_port)
        return []
    except Exception as exc:
        logger.warning("Errore interrogazione BDT da %s:%d: %s", bbmd_ip, bbmd_port, exc)
        return []
    finally:
        if transport and not transport.is_closing():
            transport.close()


async def read_fdt(bbmd_ip: str, bbmd_port: int = 47808, timeout: float = 3.0) -> list[dict[str, Any]]:
    """
    Legge la Foreign Device Table (FDT) da un BBMD BACnet/IP
    inviando un messaggio BVLL Read-Foreign-Device-Table (0x81 0x06 0x00 0x04).
    """
    import struct
    loop = asyncio.get_running_loop()
    transport: Optional[asyncio.DatagramTransport] = None
    try:
        transport_raw, protocol = await loop.create_datagram_endpoint(
            lambda: _BVLLResponseProtocol(),
            local_addr=("0.0.0.0", 0)
        )
        transport = transport_raw  # type: ignore[assignment]
        # Pacchetto BVLL Read-FDT: Type=0x81, Func=0x06, Len=0x0004
        req = bytes([0x81, 0x06, 0x00, 0x04])
        transport.sendto(req, (bbmd_ip, bbmd_port))
        data, _ = await asyncio.wait_for(protocol.fut, timeout=timeout)
        if len(data) >= 4 and data[0] == 0x81:
            func = data[1]
            length = struct.unpack("!H", data[2:4])[0]
            if func == 0x07:  # Read-FDT-Ack
                payload = data[4:length]
                return decode_fdt_payload(payload)
            elif func == 0x00:  # BVLL-Result
                res_code = struct.unpack("!H", data[4:6])[0] if len(data) >= 6 else -1
                logger.warning("BBMD %s:%d ha risposto con BVLL-Result NAK: 0x%04X", bbmd_ip, bbmd_port, res_code)
        return []
    except asyncio.TimeoutError:
        logger.debug("Timeout nella lettura FDT da BBMD %s:%d", bbmd_ip, bbmd_port)
        return []
    except Exception as exc:
        logger.warning("Errore interrogazione FDT da %s:%d: %s", bbmd_ip, bbmd_port, exc)
        return []
    finally:
        if transport and not transport.is_closing():
            transport.close()


async def get_bbmd_tables(bbmd_ip: str, bbmd_port: int = 47808, timeout: float = 3.0) -> dict[str, Any]:
    """
    Interroga un router BBMD estraendo sia la tabella BDT che la tabella FDT in parallelo.
    """
    bdt_res, fdt_res = await asyncio.gather(
        read_bdt(bbmd_ip, bbmd_port, timeout=timeout),
        read_fdt(bbmd_ip, bbmd_port, timeout=timeout),
        return_exceptions=True,
    )
    bdt = bdt_res if isinstance(bdt_res, list) else []
    fdt = fdt_res if isinstance(fdt_res, list) else []
    err = None
    if isinstance(bdt_res, Exception):
        err = f"BDT: {bdt_res}"
    elif isinstance(fdt_res, Exception):
        err = f"FDT: {fdt_res}"

    return {
        "bbmd_ip": bbmd_ip,
        "bbmd_port": bbmd_port,
        "bdt": bdt,
        "fdt": fdt,
        "error": err,
    }

