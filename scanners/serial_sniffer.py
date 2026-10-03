"""
BHAM – Serial Sniffer (RS485 Passive / Stealth Engine)
======================================================
Pure read-only (Zero-TX) listener on RS485 half-duplex buses.
Does NOT transmit any bytes on the wire, preventing bus collisions
with active plant PLCs / Masters (Carel, Siemens, Johnson Controls, etc.).

Features:
- Auto-Baud & Auto-Parity silent detection (9600..115200, N/E/O)
- Modbus RTU Frame Dissector (Query vs Response, FC01..FC16, FC43, Register & Values)
- BACnet MS-TP Dissector (Preamble 0x55 0xFF, Token Ring, Poll For Master, APDUs)
- Bus Health Diagnostics (FPS, Packet Error Rate %, Bus Load %, CRC errors)
- Real-time WebSocket broadcasting of frames and health telemetry
- Automatic upsert of passive devices to AppState with [SNIFFED] tag
"""

from __future__ import annotations

import asyncio
import struct
import time
from typing import TYPE_CHECKING, Any, Optional

from core.logger import logger
from data.models import (
    BACnetDevice,
    BusHealth,
    FrameDirection,
    ModbusDevice,
    Parity,
    Protocol,
    ScanStatus,
    SerialFrame,
    SerialParams,
)
from data.state import state
from scanners.base import BaseScanner

if TYPE_CHECKING:
    from api.routes import SerialSniffRequest


# ── Modbus CRC-16 (Standard 0xA001) ───────────────────────────────────────────

def calc_modbus_crc(data: bytes) -> int:
    """Calcola il CRC-16 Modbus standard (polinomio 0xA001 riflesso)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def check_modbus_crc(frame: bytes) -> bool:
    """Verifica se gli ultimi 2 byte di frame corrispondono al CRC-16 Modbus (Little-Endian)."""
    if len(frame) < 4:
        return False
    calc = calc_modbus_crc(frame[:-2])
    recv = struct.unpack_from("<H", frame, len(frame) - 2)[0]
    return calc == recv


# ── BACnet MS-TP CRC Algorithms (ANSI/ASHRAE Standard 135) ───────────────────

def calc_mstp_header_crc(data_value: int, crc_value: int) -> int:
    """Accumulatore CRC-8 per Header BACnet MS-TP (clausola 9.2)."""
    crc = crc_value ^ data_value
    crc = (crc ^ (crc << 1) ^ (crc << 2) ^ (crc << 3)
           ^ (crc << 4) ^ (crc << 5) ^ (crc << 6) ^ (crc << 7))
    return ((crc & 0xFE) ^ ((crc >> 8) & 1)) & 0xFF


def check_mstp_header_crc(header: bytes) -> bool:
    """
    Verifica l'Header CRC-8 di 6 byte:
    Type, Destination, Source, LengthMSB, LengthLSB, HeaderCRC.
    L'accumulatore iniziale è 0xFF; il valore finale invertito deve coincidere con HeaderCRC,
    oppure far passare tutti i 6 byte nell'accumulatore produce 0x55.
    """
    if len(header) < 6:
        return False
    c = 0xFF
    for b in header[:6]:
        c = calc_mstp_header_crc(b, c)
    return c == 0x55


def calc_mstp_data_crc(data: bytes) -> int:
    """Calcola il CRC-16/ISO-HDLC per il payload dati BACnet MS-TP."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return (~crc) & 0xFFFF


def check_mstp_data_crc(data_and_crc: bytes) -> bool:
    """
    Verifica se il blocco dati + 2 byte di CRC-16 produce il residuo standard 0xF0B8.
    """
    if len(data_and_crc) < 2:
        return False
    crc = 0xFFFF
    for byte in data_and_crc:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    return crc == 0xF0B8


# ── Serial Sniffer Implementation ─────────────────────────────────────────────

class SerialSniffer(BaseScanner):
    """
    Motore di ascolto passivo per bus RS485.
    Completamente asincrono e thread-safe.
    """

    def __init__(self, session_id: str) -> None:
        super().__init__(session_id)
        self._log = logger.getChild("serial_sniffer")

    async def scan(self, *args, **kwargs) -> None:
        pass  # implementa BaseScanner ABC

    async def sniff(self, req: "SerialSniffRequest") -> None:
        """Punto di ingresso principale per lo sniffing seriale."""
        import platform
        log = self._log
        state.update_session(self.session_id, status=ScanStatus.RUNNING, progress_pct=0.0)

        # ── Pre-flight: dialout / rw access check (Linux only) ────────────────
        if platform.system() == "Linux":
            from core.priv_check import has_dialout, is_admin
            import os
            port_accessible = False
            try:
                port_accessible = os.access(req.port, os.R_OK | os.W_OK)
            except Exception:
                pass

            if not is_admin() and not has_dialout() and not port_accessible:
                advice = (
                    f"La porta seriale {req.port} richiede il gruppo 'dialout'. "
                    f"Aggiungiti al gruppo (poi esegui logout/login):  "
                    f"sudo usermod -aG dialout {os.environ.get('USER', '$USER')}"
                )
                log.error("Serial sniffer: permessi dialout mancanti. %s", advice)
                state.update_session(self.session_id, error_message=advice)
                state.finish_session(self.session_id, ScanStatus.ERROR)
                return

        log.info(
            "═══ Serial RS485 Sniffer START (Zero-TX) – port=%s baud=%s proto=%s duration=%.0fs ═══",
            req.port,
            req.baudrate or "auto",
            req.protocol_filter,
            req.duration,
        )

        loop = asyncio.get_event_loop()
        # Esegue il loop di cattura in un thread del pool per non bloccare l'event loop di FastAPI
        success = await loop.run_in_executor(None, self._run_capture_loop, req)

        state.update_session(self.session_id, progress_pct=100.0)
        if success:
            state.finish_session(self.session_id, ScanStatus.COMPLETED)
        log.info("═══ Serial RS485 Sniffer FINISHED ═══")

    # ── Loop di Cattura (Thread Worker) ───────────────────────────────────────

    def _run_capture_loop(self, req: "SerialSniffRequest") -> bool:
        try:
            import serial
        except ImportError:
            self._log.error("pyserial non installato – sniffer seriale non disponibile.")
            state.update_session(self.session_id, error_message="pyserial non disponibile")
            state.finish_session(self.session_id, ScanStatus.ERROR)
            return False

        baud = req.baudrate
        parity_str = req.parity.upper() if req.parity else "AUTO"
        stopbits = req.stopbits or 1

        # 1. Auto-Lock parametri seriali se impostati su auto / 0
        if baud == 0 or parity_str == "AUTO":
            locked = self._auto_detect_params(req.port, req.protocol_filter)
            if locked:
                baud = locked["baudrate"]
                parity_str = locked["parity"]
                stopbits = locked["stopbits"]
                self._log.info(
                    "Parametri seriali AGGANCIATI: baud=%d parità=%s stopbits=%d",
                    baud, parity_str, stopbits
                )
            else:
                self._log.warning("Nessun traffico riconosciuto durante l'auto-detect. Utilizzo default 9600 8N1.")
                baud = baud or 9600
                parity_str = "N" if parity_str == "AUTO" else parity_str

        # 2. Apertura porta seriale in sola lettura (Zero-TX)
        try:
            ser = serial.Serial(
                port=req.port,
                baudrate=baud,
                bytesize=8,
                parity=parity_str,
                stopbits=stopbits,
                timeout=0.04,  # 40ms timeout per delimitare i frame tramite silenzio intercarattere
            )
        except PermissionError as exc:
            import os, platform as _pl
            if _pl.system() == "Windows":
                hint = "Su Windows prova a rieseguire BHAM come Amministratore."
            else:
                hint = (
                    f"Aggiungiti al gruppo dialout (poi logout/login): "
                    f"sudo usermod -aG dialout {os.environ.get('USER', '$USER')}"
                )
            msg = f"Permesso negato su {req.port}: {exc} – {hint}"
            self._log.error(msg)
            state.update_session(self.session_id, error_message=msg)
            state.finish_session(self.session_id, ScanStatus.ERROR)
            return False
        except Exception as exc:
            msg = f"Impossibile aprire la porta seriale {req.port}: {exc}"
            self._log.error(msg)
            state.update_session(self.session_id, error_message=msg)
            state.finish_session(self.session_id, ScanStatus.ERROR)
            return False

        # Metriche Bus Health
        start_time = time.monotonic()
        deadline = start_time + req.duration if req.duration > 0 else float("inf")
        last_health_broadcast = 0.0

        total_frames = 0
        valid_frames = 0
        crc_errors = 0
        total_bytes = 0
        active_nodes: set[int] = set()

        raw_buffer = bytearray()

        try:
            while not self.is_aborted() and time.monotonic() < deadline:
                # Lettura chunk di byte dal buffer UART con gestione Hot-Plug & disconnessioni
                chunk = None
                try:
                    chunk = ser.read(512)
                except (serial.SerialException, OSError, IOError) as exc:
                    self._log.warning(
                        "Anomalia o disconnessione hardware su %s: %s", req.port, exc
                    )
                    from api.websockets import manager
                    manager.broadcast_sync({
                        "event": "hardware_disconnect",
                        "port": req.port,
                        "message": f"Convertitore seriale {req.port} disconnesso o non raggiungibile."
                    })
                    try:
                        ser.close()
                    except Exception:
                        pass

                    # Entrata in loop di auto-recovery hot-plug
                    recovered = False
                    while not self.is_aborted() and time.monotonic() < deadline:
                        time.sleep(1.0)
                        import os
                        if os.path.exists(req.port):
                            try:
                                ser = serial.Serial(
                                    port=req.port,
                                    baudrate=baud,
                                    bytesize=8,
                                    parity=parity_str,
                                    stopbits=stopbits,
                                    timeout=0.04,
                                )
                                recovered = True
                                self._log.info(
                                    "Convertitore seriale %s RICONNESSO (Hot-Plug auto-recovery OK).", req.port
                                )
                                manager.broadcast_sync({
                                    "event": "hardware_reconnect",
                                    "port": req.port,
                                    "message": f"Convertitore seriale {req.port} ricollegato e operativo."
                                })
                                break
                            except Exception:
                                pass

                    if not recovered:
                        self._log.warning("Scansione terminata a causa della disconnessione prolungata di %s.", req.port)
                        break
                    continue

                now = time.monotonic()

                if chunk:
                    total_bytes += len(chunk)
                    raw_buffer.extend(chunk)

                    # Limitazione dimensione buffer circolare
                    if len(raw_buffer) > 4096:
                        raw_buffer = raw_buffer[-2048:]

                # Se abbiamo dati nel buffer, proviamo a estrarre frame
                if raw_buffer:
                    frames_found = self._process_buffer(
                        raw_buffer,
                        req.port,
                        baud,
                        parity_str,
                        stopbits,
                        req.protocol_filter,
                        active_nodes,
                    )
                    for frame_ok, is_valid in frames_found:
                        total_frames += 1
                        if is_valid:
                            valid_frames += 1
                        else:
                            crc_errors += 1

                # Aggiornamento periodico metriche Bus Health (ogni 500ms)
                if now - last_health_broadcast >= 0.5:
                    elapsed = max(0.1, now - start_time)
                    fps = round(valid_frames / elapsed, 1)
                    # Stima bus load: 10 bit per carattere (1 start, 8 data, 1 stop/parity)
                    bus_load = round(min(100.0, ((total_bytes * 10) / baud) / elapsed * 100), 1)
                    per = round((crc_errors / max(1, total_frames)) * 100.0, 1)

                    # Euristica Diagnostica Qualità Bus RS485 (Livello Fisico)
                    if total_frames < 5:
                        phy_status = "GOOD"
                        phy_diag = "Campionamento frame in corso / bus a riposo (quiet line)..."
                    elif per > 25.0:
                        phy_status = "CRITICAL"
                        phy_diag = (
                            "Rilevato alto tasso di errori CRC/framing (>25%): "
                            "verificare assenza resistenze di terminazione 120Ω o possibile inversione polarità morsetti A(+)/B(-)."
                        )
                    elif per > 8.0:
                        phy_status = "WARNING"
                        phy_diag = (
                            "Disturbi o jitter rilevati sul bus (errori 8-25%): "
                            "verificare schermatura cavo, terra GND di riferimento o lunghezza tratta bus."
                        )
                    elif bus_load > 85.0:
                        phy_status = "WARNING"
                        phy_diag = (
                            "Saturazione bus (>85% load): frequenza di polling Master troppo elevata o baudrate insufficiente."
                        )
                    else:
                        phy_status = "GOOD"
                        phy_diag = "Bus RS485 stabile e conforme (qualità segnale ottimale)."

                    health = BusHealth(
                        total_frames=total_frames,
                        valid_frames=valid_frames,
                        crc_errors=crc_errors,
                        packet_error_rate_pct=per,
                        frames_per_sec=fps,
                        bus_load_pct=bus_load,
                        baudrate=baud,
                        parity=parity_str,
                        active_nodes=sorted(list(active_nodes)),
                        physical_status=phy_status,
                        physical_diagnosis=phy_diag,
                    )
                    state.update_bus_health(health)
                    last_health_broadcast = now

                # Se la durata è impostata, aggiorniamo il progresso
                if req.duration > 0:
                    pct = min(99.0, round(((now - start_time) / req.duration) * 100.0, 1))
                    state.update_session(self.session_id, progress_pct=pct, found_devices=len(active_nodes))

                # Breve respiro per cedere il tempo macchina
                time.sleep(0.005)

        finally:
            try:
                ser.close()
            except Exception:
                pass

        return True

    # ── Auto-Detect Parametri Seriale ─────────────────────────────────────────

    def _auto_detect_params(self, port: str, proto_filter: str) -> Optional[dict]:
        """
        Ascolta passivamente su una sequenza di baud rate e parità.
        Aggancia i parametri appena individua frame conformi con CRC valido.
        """
        import serial

        candidate_bauds = [9600, 19200, 38400, 57600, 76800, 115200]
        candidate_parities = ["N", "E", "O"]

        for baud in candidate_bauds:
            for parity in candidate_parities:
                if self.is_aborted():
                    return None
                try:
                    ser = serial.Serial(
                        port=port,
                        baudrate=baud,
                        bytesize=8,
                        parity=parity,
                        stopbits=1,
                        timeout=0.05,
                    )
                except Exception:
                    continue

                buf = bytearray()
                t_end = time.monotonic() + 0.6  # 600ms per combinazione
                found = False

                try:
                    while time.monotonic() < t_end and not self.is_aborted():
                        chunk = ser.read(128)
                        if chunk:
                            buf.extend(chunk)
                            if len(buf) > 1024:
                                buf = buf[-512:]

                            # Controllo Modbus RTU
                            if proto_filter in ("auto", "modbus_rtu"):
                                if self._find_modbus_frame(buf) is not None:
                                    found = True
                                    break

                            # Controllo BACnet MS-TP
                            if proto_filter in ("auto", "bacnet_mstp"):
                                if self._find_mstp_frame(buf) is not None:
                                    found = True
                                    break
                finally:
                    ser.close()

                if found:
                    return {"baudrate": baud, "parity": parity, "stopbits": 1}

        return None

    # ── Elaborazione Buffer Stream ────────────────────────────────────────────

    def _process_buffer(
        self,
        buf: bytearray,
        port: str,
        baud: int,
        parity: str,
        stopbits: int,
        proto_filter: str,
        active_nodes: set[int],
    ) -> list[tuple[SerialFrame, bool]]:
        """
        Scansiona il buffer per estrarre frame Modbus o BACnet MS-TP.
        Ritorna una lista di tuple (SerialFrame, is_valid_crc).
        Rimuove dal buffer i byte consumati.
        """
        results: list[tuple[SerialFrame, bool]] = []

        while len(buf) >= 4:
            # 1. Tentativo BACnet MS-TP (Preambolo 0x55 0xFF)
            if proto_filter in ("auto", "bacnet_mstp"):
                mstp_idx = buf.find(b"\x55\xFF")
                if mstp_idx != -1:
                    # Se c'è spazzatura prima del preambolo, eliminiamola
                    if mstp_idx > 0:
                        del buf[:mstp_idx]

                    # Se mancano byte per almeno l'header, aspetta altri dati
                    if len(buf) < 8:
                        break

                    # Verifica il CRC dell'header
                    header = bytes(buf[2:8])
                    if not check_mstp_header_crc(header):
                        # Header CRC non valido: scarta solo il preambolo per avanzare
                        del buf[:2]
                        results.append((
                            SerialFrame(
                                protocol=Protocol.BACNET_MSTP,
                                direction=FrameDirection.UNKNOWN,
                                summary="BACnet MS-TP: Header CRC Error",
                                raw_hex=buf[:8].hex(" ").upper() if len(buf) >= 8 else buf.hex(" ").upper(),
                                crc_ok=False,
                            ),
                            False,
                        ))
                        continue

                    parsed = self._parse_mstp_frame(buf, port, active_nodes)
                    if parsed is not None:
                        frame, consumed, is_valid = parsed
                        del buf[:consumed]
                        state.record_serial_frame(frame)
                        results.append((frame, is_valid))
                        continue
                    else:
                        # Header CRC è valido ma il payload non è completo, aspetta altri dati
                        break

            # 2. Tentativo Modbus RTU
            if proto_filter in ("auto", "modbus_rtu"):
                mb_result = self._find_modbus_frame(buf)
                if mb_result is not None:
                    start_idx, end_idx = mb_result
                    raw_frame = bytes(buf[start_idx:end_idx])
                    del buf[:end_idx]

                    frame = self._dissect_modbus_frame(
                        raw_frame, port, baud, parity, stopbits, active_nodes
                    )
                    state.record_serial_frame(frame)
                    results.append((frame, True))
                    continue

            # Se non abbiamo agganciato nulla nei primi byte e il buffer cresce, avanziamo di 1 byte
            if len(buf) > 512:
                del buf[:1]
            else:
                break

        return results

    # ── Dissettore Modbus RTU ─────────────────────────────────────────────────

    def _find_modbus_frame(self, data: bytes | bytearray) -> Optional[tuple[int, int]]:
        """
        Cerca un sotto-intervallo [start:end] con CRC-16 Modbus valido.
        I frame Modbus tipici variano da 4 a 256 byte.
        """
        n = len(data)
        for start in range(min(n - 3, 64)):
            # I codici funzione Modbus standard sono compresi tra 1 e 127 (o 128..255 per eccezioni)
            if start + 1 < n and data[start] == 0:
                continue  # Broadcast slave ID 0 ha senso solo se c'è funzione valida
            for end in range(start + 4, min(start + 256, n) + 1):
                if check_modbus_crc(data[start:end]):
                    return (start, end)
        return None

    def _dissect_modbus_frame(
        self,
        raw: bytes,
        port: str,
        baud: int,
        parity: str,
        stopbits: int,
        active_nodes: set[int],
    ) -> SerialFrame:
        """Disseziona un frame Modbus RTU e cataloga il dispositivo in AppState."""
        slave_id = raw[0]
        fc = raw[1]
        raw_hex = raw.hex(" ").upper()
        active_nodes.add(slave_id)

        direction = FrameDirection.UNKNOWN
        function_name = f"FC{fc:02d}"
        summary = ""
        data_dict: dict[str, Any] = {"raw_len": len(raw)}

        # Gestione Eccezioni (bit 7 impostato)
        if fc >= 0x80:
            err_fc = fc - 0x80
            exc_code = raw[2] if len(raw) > 2 else 0
            direction = FrameDirection.SLAVE_TO_MASTER
            function_name = f"FC{err_fc:02d} EXCEPTION"
            exc_labels = {
                1: "ILLEGAL_FUNCTION",
                2: "ILLEGAL_DATA_ADDRESS",
                3: "ILLEGAL_DATA_VALUE",
                4: "SLAVE_DEVICE_FAILURE",
            }
            summary = f"Slave {slave_id} ➔ Exception FC{err_fc:02d}: {exc_labels.get(exc_code, f'Code {exc_code}')}"
            data_dict["exception_code"] = exc_code

        # FC01 (Read Coils) / FC02 (Read Discrete Inputs)
        elif fc in (1, 2):
            kind = "Coils" if fc == 1 else "Discrete Inputs"
            function_name = f"FC{fc:02d} Read {kind}"
            if len(raw) == 8:
                # Query del Master: [ID, FC, StartHi, StartLo, CountHi, CountLo, CRC, CRC]
                start_addr = (raw[2] << 8) | raw[3]
                count = (raw[4] << 8) | raw[5]
                direction = FrameDirection.MASTER_TO_SLAVE
                summary = f"Master ➔ Slave {slave_id}: Read {kind} [{start_addr}..{start_addr + count - 1}] (cnt={count})"
                data_dict["start_addr"] = start_addr
                data_dict["count"] = count
            else:
                # Risposta dello Slave: [ID, FC, ByteCount, Data..., CRC, CRC]
                byte_count = raw[2]
                direction = FrameDirection.SLAVE_TO_MASTER
                summary = f"Slave {slave_id} ➔ Master: {kind} {byte_count} byte(s)"
                data_dict["byte_count"] = byte_count

        # FC03 (Read Holding Registers) / FC04 (Read Input Registers)
        elif fc in (3, 4):
            kind = "Holding Regs" if fc == 3 else "Input Regs"
            function_name = f"FC{fc:02d} Read {kind}"
            if len(raw) == 8:
                # Query del Master: [ID, FC, StartHi, StartLo, CountHi, CountLo, CRC, CRC]
                start_addr = (raw[2] << 8) | raw[3]
                count = (raw[4] << 8) | raw[5]
                direction = FrameDirection.MASTER_TO_SLAVE
                summary = f"Master ➔ Slave {slave_id}: Read {kind} [{start_addr}..{start_addr + count - 1}] (cnt={count})"
                data_dict["start_addr"] = start_addr
                data_dict["count"] = count
            else:
                # Risposta dello Slave: [ID, FC, ByteCount, Reg1Hi, Reg1Lo..., CRC, CRC]
                byte_count = raw[2]
                reg_count = byte_count // 2
                regs_values: list[int] = []
                for i in range(reg_count):
                    val = struct.unpack_from(">H", raw, 3 + i * 2)[0]
                    regs_values.append(val)

                direction = FrameDirection.SLAVE_TO_MASTER
                summary = f"Slave {slave_id} ➔ Master: {kind} {reg_count} reg(s): {regs_values[:4]}{'…' if reg_count > 4 else ''}"
                data_dict["registers"] = regs_values

                # Upsert automatico del dispositivo scoperto nello stato globale
                dev_regs = {f"reg_{idx}": val for idx, val in enumerate(regs_values)}
                dev = ModbusDevice(
                    slave_id=slave_id,
                    protocol=Protocol.MODBUS_RTU,
                    serial_params=SerialParams(
                        port=port,
                        baudrate=baud,
                        parity=Parity(parity),
                        stopbits=stopbits,
                    ),
                    registers=dev_regs,
                    tags=["sniffed", "passive"],
                )
                state.upsert_modbus(dev)

        # FC05 (Write Single Coil) / FC06 (Write Single Register)
        elif fc in (5, 6):
            kind = "Single Coil" if fc == 5 else "Single Reg"
            function_name = f"FC{fc:02d} Write {kind}"
            addr = (raw[2] << 8) | raw[3]
            val = (raw[4] << 8) | raw[5]
            summary = f"Master/Slave: Write {kind} addr={addr} val=0x{val:04X} ({val})"
            direction = FrameDirection.MASTER_TO_SLAVE
            data_dict["addr"] = addr
            data_dict["val"] = val

        # FC15 (Write Multiple Coils) / FC16 (Write Multiple Registers)
        elif fc in (15, 16):
            kind = "Multiple Coils" if fc == 15 else "Multiple Regs"
            function_name = f"FC{fc:02d} Write {kind}"
            addr = (raw[2] << 8) | raw[3]
            count = (raw[4] << 8) | raw[5]
            if len(raw) == 8:
                direction = FrameDirection.SLAVE_TO_MASTER
                summary = f"Slave {slave_id} ➔ Master: Write {kind} ACK addr={addr} count={count}"
            else:
                direction = FrameDirection.MASTER_TO_SLAVE
                summary = f"Master ➔ Slave {slave_id}: Write {kind} addr={addr} count={count}"
            data_dict["addr"] = addr
            data_dict["count"] = count

        # FC43 (ME Device Identification)
        elif fc == 43:
            function_name = "FC43 ME Device Identification"
            direction = FrameDirection.SLAVE_TO_MASTER if len(raw) > 10 else FrameDirection.MASTER_TO_SLAVE
            summary = f"Slave {slave_id} Device Identification (ME 0x0E)"

        else:
            summary = f"Modbus Frame: Slave {slave_id} FC0x{fc:02X} len={len(raw)}"

        return SerialFrame(
            protocol=Protocol.MODBUS_RTU,
            direction=direction,
            source_addr="Master" if direction == FrameDirection.MASTER_TO_SLAVE else str(slave_id),
            dest_addr=str(slave_id) if direction == FrameDirection.MASTER_TO_SLAVE else "Master",
            function_code=fc,
            function_name=function_name,
            summary=summary,
            raw_hex=raw_hex,
            crc_ok=True,
            data=data_dict,
        )

    # ── Dissettore BACnet MS-TP ───────────────────────────────────────────────

    def _find_mstp_frame(self, data: bytes | bytearray) -> Optional[int]:
        """Verifica la presenza di un preambolo MS-TP con Header CRC valido."""
        idx = data.find(b"\x55\xFF")
        if idx != -1 and len(data) >= idx + 8:
            if check_mstp_header_crc(data[idx + 2 : idx + 8]):
                return idx
        return None

    def _parse_mstp_frame(
        self, buf: bytearray, port: str, active_nodes: set[int]
    ) -> Optional[tuple[SerialFrame, int, bool]]:
        """
        Decodifica un frame BACnet MS-TP dal buffer se l'header è integro.
        Ritorna (SerialFrame, byte_consumati, is_valid_crc) oppure None se mancano byte.
        """
        if len(buf) < 8:
            return None  # attendiamo almeno l'header completo

        header = bytes(buf[2:8])
        if not check_mstp_header_crc(header):
            return None  # header CRC non valido

        frame_type = header[0]
        dest_mac = header[1]
        src_mac = header[2]
        data_len = (header[3] << 8) | header[4]

        # Lunghezza totale attesa: 2 (preamble) + 6 (header) + data_len + (2 se data_len > 0)
        total_len = 8 + data_len + (2 if data_len > 0 else 0)
        if len(buf) < total_len:
            return None  # attendiamo che arrivi tutto il payload dati

        raw_frame = bytes(buf[:total_len])
        data_crc_ok = True

        if data_len > 0:
            data_block = bytes(buf[8:total_len])
            data_crc_ok = check_mstp_data_crc(data_block)

        # Mappatura nodi attivi
        active_nodes.add(src_mac)
        if dest_mac != 255:
            active_nodes.add(dest_mac)

        type_names = {
            0: "Token",
            1: "Poll For Master",
            2: "Reply To Poll For Master",
            3: "Test_Request",
            4: "Test_Response",
            5: "BACnet Data Expecting Reply",
            6: "BACnet Data Not Expecting Reply",
            7: "Reply Postponed",
        }
        type_str = type_names.get(frame_type, f"Frame Type {frame_type}")

        direction = FrameDirection.UNKNOWN
        if frame_type == 0:
            direction = FrameDirection.TOKEN
            summary = f"Token Passing: MAC {src_mac} ➔ MAC {dest_mac}"
        elif frame_type == 1:
            direction = FrameDirection.POLL
            summary = f"Poll For Master: MAC {src_mac} interrogating MAC {dest_mac}"
        elif frame_type == 2:
            direction = FrameDirection.SLAVE_TO_MASTER
            summary = f"Reply To Poll: MAC {src_mac} ACK to MAC {dest_mac}"
        elif frame_type in (5, 6):
            direction = FrameDirection.BROADCAST if dest_mac == 255 else FrameDirection.MASTER_TO_SLAVE
            summary = f"{type_str} ({data_len} bytes): MAC {src_mac} ➔ MAC {dest_mac}"
        else:
            summary = f"MS-TP {type_str}: MAC {src_mac} ➔ MAC {dest_mac}"

        # Inserimento passivo nel catalogo BACnet per il MAC sorgente
        dev = BACnetDevice(
            device_id=src_mac,
            protocol=Protocol.BACNET_MSTP,
            address=f"MS/TP MAC:{src_mac}",
            tags=["sniffed", "passive", f"mstp_mac_{src_mac}"],
        )
        state.upsert_bacnet(dev)

        frame = SerialFrame(
            protocol=Protocol.BACNET_MSTP,
            direction=direction,
            source_addr=str(src_mac),
            dest_addr=str(dest_mac) if dest_mac != 255 else "Broadcast",
            function_code=frame_type,
            function_name=type_str,
            summary=summary,
            raw_hex=raw_frame[:32].hex(" ").upper() + ("…" if len(raw_frame) > 32 else ""),
            crc_ok=data_crc_ok,
            data={
                "frame_type": frame_type,
                "src_mac": src_mac,
                "dest_mac": dest_mac,
                "data_len": data_len,
            },
        )
        return (frame, total_len, data_crc_ok)
