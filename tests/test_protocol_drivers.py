"""
BHAM – Test dei driver di protocollo contro le librerie reali.

Il Simulatore d'Impianto Virtuale intercetta le operazioni Modbus prima che
raggiungano pymodbus: ottimo per provare la logica applicativa, inutile per
verificare che l'uso delle API della libreria sia ancora corretto. L'avanzamento
a pymodbus 3.16 lo ha dimostrato: `count` è diventato keyword-only, `slave` è
stato rinominato `device_id`, `pymodbus.mei_message` è stato spostato e
`execute()` ha cambiato firma — e tutti i 162 test preesistenti continuavano a
passare, mentre in campo ogni lettura reale avrebbe sollevato TypeError.

Qui il percorso reale viene esercitato davvero: viene avviato un server Modbus
TCP di pymodbus su loopback con un datastore noto, e le funzioni di BHAM ci
parlano sopra con il simulatore disattivato. Lo stesso vale per i generatori di
report, verificati sull'artefatto prodotto e non sul fatto che non sollevino
eccezioni.
"""

from __future__ import annotations

import asyncio
import socket
import sys
import threading
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.simulator import simulator

#: Valori noti caricati nel datastore del server di prova.
HOLDING = [1111, 2222, 3333, 4444, 5555]
INPUT_REGS = [9001, 9002, 9003]


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class ModbusTestServer:
    """
    Server Modbus TCP reale di pymodbus, su loopback, in un thread dedicato.

    Usa l'API `SimData`/`SimDevice`: il datastore legacy
    (`ModbusSequentialDataBlock`, `ModbusServerContext`) è deprecato in
    pymodbus 3.16 e verrà rimosso in 4.x.
    """

    def __init__(self) -> None:
        self.port = _free_port()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._server = None

    def start(self, timeout: float = 20.0) -> None:
        import time
        from pymodbus.server import ModbusTcpServer
        from pymodbus.simulator import DataType, SimData, SimDevice

        # I quattro blocchi sono, in ordine: coils, discrete inputs,
        # holding registers, input registers.
        coils = [SimData(0, values=[1, 0, 1, 1, 0], datatype=DataType.BITS)]
        discrete = [SimData(0, values=[1, 0, 1, 1, 0], datatype=DataType.BITS)]
        holding = [SimData(0, values=list(HOLDING), datatype=DataType.REGISTERS)]
        inputs = [SimData(0, values=list(INPUT_REGS), datatype=DataType.REGISTERS)]
        device = SimDevice(1, simdata=(coils, discrete, holding, inputs))

        ready = threading.Event()

        def _run() -> None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            async def _serve() -> None:
                self._server = ModbusTcpServer(
                    device, address=("127.0.0.1", self.port)
                )
                ready.set()
                await self._server.serve_forever()

            try:
                self._loop.run_until_complete(_serve())
            except Exception:
                ready.set()
            finally:
                self._loop.close()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        if not ready.wait(timeout):
            raise RuntimeError("il server Modbus di prova non si è avviato")

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.3):
                    return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError("il server Modbus di prova non accetta connessioni")

    def stop(self) -> None:
        if self._server is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self._server.shutdown())
            )
        if self._thread is not None:
            self._thread.join(timeout=10)


@unittest.skipUnless(
    __import__("importlib").util.find_spec("pymodbus") is not None,
    "pymodbus non disponibile",
)
class TestModbusAgainstRealServer(unittest.TestCase):
    """
    Esercita il percorso pymodbus reale di BHAM. Con il simulatore attivo questi
    test non proverebbero nulla: viene quindi disattivato esplicitamente.
    """

    @classmethod
    def setUpClass(cls):
        cls.server = ModbusTestServer()
        cls.server.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self.assertFalse(
            simulator.is_active,
            "il simulatore deve essere spento: altrimenti pymodbus non viene esercitato",
        )

    def _read(self, **kwargs):
        from scanners.field_tools import modbus_quick_read
        params = dict(
            protocol="tcp", ip="127.0.0.1", tcp_port=self.server.port,
            slave_id=1, timeout=3.0,
        )
        params.update(kwargs)
        return asyncio.run(modbus_quick_read(**params))

    def test_read_holding_registers(self):
        res = self._read(function_code=3, address=0, count=5)
        self.assertTrue(res["success"], res.get("error"))
        self.assertFalse(res.get("simulated"), "la lettura non deve venire dal simulatore")
        self.assertEqual(res["registers"], HOLDING)

    def test_read_input_registers(self):
        res = self._read(function_code=4, address=0, count=3)
        self.assertTrue(res["success"], res.get("error"))
        self.assertEqual(res["registers"], INPUT_REGS)

    def test_read_coils(self):
        """
        Prova la forma della chiamata FC1 contro il server reale. La semantica a
        campo di bit di `SimData` non permette di fissare i singoli coil, quindi
        si verifica che la chiamata vada a buon fine e restituisca il numero di
        bit richiesto: è questo che smaschera un rename di parametro.
        """
        res = self._read(function_code=1, address=0, count=5)
        self.assertTrue(res["success"], res.get("error"))
        self.assertFalse(res.get("simulated"))
        self.assertGreaterEqual(len(res["coils"]), 5)

    def test_read_discrete_inputs(self):
        res = self._read(function_code=2, address=0, count=5)
        self.assertTrue(res["success"], res.get("error"))
        self.assertFalse(res.get("simulated"))
        self.assertGreaterEqual(len(res["coils"]), 5)

    def test_read_offset_and_count_are_honoured(self):
        """`count` è diventato keyword-only: un errore qui lo smaschera."""
        res = self._read(function_code=3, address=2, count=2)
        self.assertTrue(res["success"], res.get("error"))
        self.assertEqual(res["registers"], HOLDING[2:4])

    def _arm_safe_mode(self):
        """
        Le forzature su bus di campo sono bloccate dal Safe Mode Interlock: il
        test lo arma come farebbe l'operatore, con operatore e commessa, e lo
        disarma al termine. Il blocco predefinito è comportamento voluto.
        """
        from core.safe_mode import safe_mode
        safe_mode.arm(operator="Test Driver", job_order="COMM-DRV-TEST", duration_minutes=5)
        self.addCleanup(safe_mode.disarm)

    def test_write_single_register_round_trip(self):
        self._arm_safe_mode()
        from scanners.field_tools import modbus_quick_write
        wr = asyncio.run(modbus_quick_write(
            protocol="tcp", ip="127.0.0.1", tcp_port=self.server.port,
            slave_id=1, function_code=6, address=1, values=[4242], timeout=3.0,
        ))
        self.assertTrue(wr["success"], wr.get("error"))
        back = self._read(function_code=3, address=1, count=1)
        self.assertEqual(back["registers"], [4242])

    def test_write_multiple_registers_round_trip(self):
        self._arm_safe_mode()
        from scanners.field_tools import modbus_quick_write
        wr = asyncio.run(modbus_quick_write(
            protocol="tcp", ip="127.0.0.1", tcp_port=self.server.port,
            slave_id=1, function_code=16, address=3, values=[7001, 7002], timeout=3.0,
        ))
        self.assertTrue(wr["success"], wr.get("error"))
        back = self._read(function_code=3, address=3, count=2)
        self.assertEqual(back["registers"], [7001, 7002])

    def test_smart_register_scan_finds_the_populated_registers(self):
        """
        Copre lo Smart Register Scan sul percorso TCP reale: è il blocco che usa
        le letture a blocchi e la ricaduta sul singolo registro, tutte riscritte
        per la firma keyword-only di pymodbus 3.16.
        """
        from api.routes import modbus_smart_scan
        from api.schemas import ModbusSmartScanBody

        res = asyncio.run(modbus_smart_scan(ModbusSmartScanBody(
            slave_id=1, protocol="tcp", ip="127.0.0.1", tcp_port=self.server.port,
        )))
        self.assertIsNone(res.get("error"), res.get("error"))
        registers = res.get("registers", [])
        self.assertTrue(registers, "lo smart scan non ha trovato alcun registro popolato")

        # Lo scan censisce sia holding sia input: la chiave deve tenere conto
        # del tipo, altrimenti gli indirizzi omonimi si sovrascrivono.
        found = {(r["address"], r["type"]): r["raw_dec"] for r in registers}
        for addr, expected in enumerate(HOLDING):
            key = (addr, "holding")
            if key in found:
                with self.subTest(holding=addr):
                    self.assertEqual(found[key], expected)
        for addr, expected in enumerate(INPUT_REGS):
            key = (addr, "input")
            if key in found:
                with self.subTest(input=addr):
                    self.assertEqual(found[key], expected)
        self.assertIn((0, "holding"), found, "l'holding 0 (valore 1111) doveva essere rilevato")

    def test_write_is_refused_while_safe_mode_is_locked(self):
        """L'interlock deve bloccare la forzatura anche su un bus reale."""
        from core.safe_mode import safe_mode
        from scanners.field_tools import modbus_quick_write
        self.assertFalse(safe_mode.is_armed, "il Safe Mode deve partire bloccato")
        wr = asyncio.run(modbus_quick_write(
            protocol="tcp", ip="127.0.0.1", tcp_port=self.server.port,
            slave_id=1, function_code=6, address=0, values=[1], timeout=3.0,
        ))
        self.assertFalse(wr["success"])
        self.assertIn("Safe Mode", wr.get("error", ""))

    def test_tcp_scan_discovers_the_real_server(self):
        """Il motore di scansione Modbus TCP deve censire il server di prova."""
        from api.schemas import ModbusTCPScanRequest
        from scanners.modbus import ModbusScanner
        from data.state import state

        session = state.new_session(
            __import__("data.models", fromlist=["Protocol"]).Protocol.MODBUS_TCP, {}
        )
        scanner = ModbusScanner(session_id=session.id)
        scanner.reset_abort()
        req = ModbusTCPScanRequest(
            hosts=["127.0.0.1"], tcp_port=self.server.port, slave_ids=[1],
        )
        asyncio.run(scanner.scan_tcp(req))
        found = [
            d for d in state.modbus_devices.values()
            if d.ip == "127.0.0.1" and d.tcp_port == self.server.port
        ]
        self.assertTrue(found, "il server Modbus reale non è stato rilevato dalla scansione")


class TestReportGenerators(unittest.TestCase):
    """
    I generatori di report vanno verificati sull'artefatto prodotto: reportlab 5
    è un avanzamento major e un'API cambiata non si vede dal semplice fatto che
    la funzione non solleva eccezioni.
    """

    def _populate(self):
        from data.models import ModbusDevice, SerialParams, Parity
        from data.state import state
        state.upsert_modbus(ModbusDevice(
            slave_id=7,
            serial_params=SerialParams(port="/dev/ttyUSB0", baudrate=9600, parity=Parity.NONE, stopbits=1),
            vendor_name="Collaudo S.p.A.",
            product_code="BHAM-TEST",
        ))

    def test_pdf_is_a_valid_document(self):
        import tempfile
        from reports.pdf import generate_pdf
        self._populate()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "verbale.pdf"
            generate_pdf(str(out))
            self.assertTrue(out.is_file(), "nessun PDF prodotto")
            raw = out.read_bytes()
            self.assertGreater(len(raw), 1000, "PDF sospettosamente piccolo")
            self.assertTrue(raw.startswith(b"%PDF-"), "intestazione PDF assente")
            self.assertIn(b"%%EOF", raw[-2048:], "PDF non terminato correttamente")

    def test_excel_reopens_with_expected_sheets(self):
        import tempfile
        import openpyxl
        from reports.excel import generate_excel
        self._populate()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "verbale.xlsx"
            generate_excel(str(out))
            self.assertTrue(out.is_file(), "nessun Excel prodotto")
            wb = openpyxl.load_workbook(str(out))
            self.assertTrue(wb.sheetnames, "cartella di lavoro senza fogli")
            wb.close()


class TestDriverApiSurface(unittest.TestCase):
    """
    Presidio minimo sulle API delle librerie di protocollo che BHAM usa con
    import tardivi: un rename a monte si manifesterebbe altrimenti solo in
    cantiere, all'apertura della funzione.
    """

    def test_pymodbus_read_write_signatures(self):
        import inspect
        from pymodbus.client import ModbusTcpClient
        for name in ("read_holding_registers", "read_input_registers",
                     "read_coils", "read_discrete_inputs"):
            with self.subTest(method=name):
                params = inspect.signature(getattr(ModbusTcpClient, name)).parameters
                self.assertIn("device_id", params)
                self.assertEqual(params["count"].kind, inspect.Parameter.KEYWORD_ONLY)

    def test_pymodbus_device_information_request_is_importable(self):
        from pymodbus.pdu.mei_message import ReadDeviceInformationRequest
        import inspect
        params = inspect.signature(ReadDeviceInformationRequest.__init__).parameters
        self.assertIn("dev_id", params)

    def test_pymodbus_execute_takes_no_response_expected_first(self):
        import inspect
        from pymodbus.client import ModbusTcpClient
        params = list(inspect.signature(ModbusTcpClient.execute).parameters)
        self.assertEqual(params[1], "no_response_expected")

    def test_bacpypes3_entry_points_used_by_the_scanner(self):
        from bacpypes3.pdu import Address  # noqa: F401
        from bacpypes3.app import Application  # noqa: F401
        from bacpypes3.primitivedata import ObjectIdentifier  # noqa: F401

    def test_scapy_entry_points_used_by_the_sniffer(self):
        from scapy.layers.l2 import ARP  # noqa: F401
        import inspect
        from scapy.all import sniff
        params = inspect.signature(sniff).parameters
        for expected in ("iface", "prn", "store"):
            with self.subTest(param=expected):
                self.assertTrue(
                    expected in params or any(
                        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
                    )
                )


if __name__ == "__main__":
    unittest.main()
