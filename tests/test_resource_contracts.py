"""
BHAM – Test di contratto API e mutua esclusione delle risorse di campo.

Due famiglie di regressione introdotte dal controllo generale v1.2.5:

1. **Contratti di risposta.** La suite esistente invoca le funzioni handler
   direttamente, quindi la validazione di FastAPI contro il `response_model`
   dichiarato non veniva mai esercitata. Per questo era sopravvissuto un
   `POST /api/v1/scan/abort` che rispondeva HTTP 500: l'handler restituiva un
   intero dove lo schema dichiarava `list[str]`. Qui l'uscita degli handler
   viene validata contro il modello realmente dichiarato sulla route.

2. **Risorse esclusive.** Porta seriale RS485, socket BACnet/IP e KNXnet/IP
   ammettono un solo utilizzatore: l'avvio concorrente deve essere rifiutato
   con un errore azionabile, non produrre letture corrotte.
"""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import HTTPException
from pydantic import TypeAdapter

from api import routes
from api.schemas import SerialSniffRequest
from core import resource_guard
from data.models import Protocol, ScanStatus
from data.state import AppState, state
from scanners import base as scanner_base


def _route_response_model(path: str, method: str):
    """Modello di risposta realmente dichiarato sulla route, come fa FastAPI."""
    for route in routes.router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return getattr(route, "response_model", None)
    raise AssertionError(f"route {method} {path} non trovata")


def _assert_matches_route_model(path: str, method: str, payload) -> None:
    """Valida il payload contro il response_model, come farebbe FastAPI."""
    model = _route_response_model(path, method)
    assert model is not None, f"{method} {path} non dichiara un response_model"
    TypeAdapter(model).validate_python(payload)


class TestResponseContracts(unittest.TestCase):
    """Gli handler devono rispettare il response_model che dichiarano."""

    def setUp(self):
        resource_guard.reset()

    def tearDown(self):
        resource_guard.reset()

    def test_global_abort_matches_its_declared_model(self):
        """
        Regressione: l'arresto d'emergenza globale rispondeva HTTP 500 perché
        `abort_all()` restituiva un int e lo schema dichiara `list[str]`.
        """
        scanner_base.abort_session("sessione-di-prova")
        payload = asyncio.run(routes.abort_all_scans())
        _assert_matches_route_model("/scan/abort", "POST", payload)
        self.assertTrue(payload["aborted"])
        self.assertIsInstance(payload["sessions"], list)

    def test_single_abort_matches_its_declared_model(self):
        payload = asyncio.run(routes.abort_scan("sessione-inesistente"))
        _assert_matches_route_model("/scan/abort/{session_id}", "POST", payload)

    def test_resource_listing_matches_its_declared_model(self):
        resource_guard.acquire(
            resource_guard.serial_resource("/dev/ttyUSB7"), "s-1", "Sniffer passivo RS485"
        )
        payload = asyncio.run(routes.get_resource_claims())
        _assert_matches_route_model("/system/resources", "GET", payload)
        self.assertEqual(payload[0]["resource"], "serial:/dev/ttyUSB7")

    def test_health_matches_its_declared_model(self):
        payload = asyncio.run(routes.health())
        _assert_matches_route_model("/health", "GET", payload)

    def test_every_scan_route_declares_a_response_model(self):
        """Senza response_model non esiste contratto da verificare."""
        missing = [
            f"{sorted(r.methods)} {r.path}"
            for r in routes.router.routes
            if getattr(r, "path", "").startswith("/scan")
            and getattr(r, "methods", None)
            and getattr(r, "response_model", None) is None
        ]
        self.assertEqual(missing, [])


class TestAbortRegistry(unittest.TestCase):
    """Il registro degli abort non deve crescere per tutta la giornata."""

    def test_abort_all_reports_only_sessions_it_stopped(self):
        scanner_base.release_session("x1")
        scanner_base.release_session("x2")
        scanner_base.abort_session("x1")          # già abortita
        scanner = _DummyScanner("x2")
        scanner.reset_abort()                     # attiva
        stopped = scanner_base.abort_all()
        self.assertIn("x2", stopped)
        self.assertNotIn("x1", stopped, "una sessione già abortita non va ricontata")
        scanner_base.release_session("x1")
        scanner_base.release_session("x2")

    def test_release_session_prunes_the_registry(self):
        before = scanner_base.tracked_sessions()
        scanner = _DummyScanner("da-liberare")
        scanner.reset_abort()
        self.assertEqual(scanner_base.tracked_sessions(), before + 1)
        scanner_base.release_session("da-liberare")
        self.assertEqual(scanner_base.tracked_sessions(), before)

    def test_abort_session_signals_only_once(self):
        scanner_base.release_session("y1")
        self.assertTrue(scanner_base.abort_session("y1"))
        self.assertFalse(scanner_base.abort_session("y1"))
        scanner_base.release_session("y1")


class _DummyScanner(scanner_base.BaseScanner):
    async def scan(self, *args, **kwargs) -> None:  # pragma: no cover
        return None


class TestResourceGuard(unittest.TestCase):
    """Registro di mutua esclusione sulle risorse fisiche."""

    def setUp(self):
        resource_guard.reset()

    def tearDown(self):
        resource_guard.reset()

    def test_second_session_on_same_port_is_refused(self):
        key = resource_guard.serial_resource("/dev/ttyUSB0")
        resource_guard.acquire(key, "s-1", "Sniffer passivo RS485")
        with self.assertRaises(resource_guard.ResourceBusyError) as ctx:
            resource_guard.acquire(key, "s-2", "Scansione Modbus RTU")
        detail = ctx.exception.as_detail()
        self.assertEqual(detail["conflicting_session_id"], "s-1")
        self.assertIn("Sniffer passivo RS485", detail["detail"])
        self.assertIn("abort", detail["hint"])

    def test_different_ports_do_not_conflict(self):
        resource_guard.acquire(resource_guard.serial_resource("/dev/ttyUSB0"), "a", "A")
        resource_guard.acquire(resource_guard.serial_resource("/dev/ttyUSB1"), "b", "B")
        self.assertEqual(len(resource_guard.claims()), 2)

    def test_same_session_reacquire_is_idempotent(self):
        key = resource_guard.serial_resource("/dev/ttyUSB0")
        first = resource_guard.acquire(key, "s-1", "Sniffer")
        again = resource_guard.acquire(key, "s-1", "Sniffer")
        self.assertEqual(first.acquired_at, again.acquired_at)
        self.assertEqual(len(resource_guard.claims()), 1)

    def test_release_if_owner_protects_other_sessions(self):
        key = resource_guard.serial_resource("/dev/ttyUSB0")
        resource_guard.acquire(key, "owner", "Owner")
        self.assertFalse(resource_guard.release_if_owner(key, "intruso"))
        self.assertIsNotNone(resource_guard.claim_for(key))
        self.assertTrue(resource_guard.release_if_owner(key, "owner"))
        self.assertIsNone(resource_guard.claim_for(key))

    def test_release_session_frees_every_resource_it_holds(self):
        resource_guard.acquire(resource_guard.serial_resource("/dev/ttyUSB0"), "s", "A")
        resource_guard.acquire(resource_guard.BACNET_IP, "s", "B")
        freed = resource_guard.release_session("s")
        self.assertEqual(len(freed), 2)
        self.assertEqual(resource_guard.claims(), [])

    def test_resource_keys_are_stable_and_readable(self):
        self.assertEqual(resource_guard.serial_resource("COM3"), "serial:COM3")
        self.assertEqual(resource_guard.serial_resource(None), "serial:non-specificata")
        self.assertEqual(resource_guard.iface_resource("arp", ""), "arp:auto")
        self.assertEqual(resource_guard.iface_resource("arp", "eth0"), "arp:eth0")


class TestScanRoutesRespectTheGuard(unittest.TestCase):
    """Le route di avvio devono rifiutare il conflitto senza effetti collaterali."""

    def setUp(self):
        resource_guard.reset()

    def tearDown(self):
        resource_guard.reset()

    def test_busy_serial_port_is_refused_with_409(self):
        port = "/dev/ttyUSB-test"
        resource_guard.acquire(
            resource_guard.serial_resource(port), "in-corso", "Sniffer passivo RS485"
        )
        req = SerialSniffRequest(port=port, duration=1.0)
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(routes.start_serial_sniff(req))
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["conflicting_session_id"], "in-corso")

    def test_refused_start_leaves_no_ghost_session(self):
        """
        Il controllo avviene prima di creare la sessione: un conflitto non deve
        lasciare nello storico una scansione mai partita.
        """
        port = "/dev/ttyUSB-test2"
        resource_guard.acquire(resource_guard.serial_resource(port), "in-corso", "Sniffer")
        before = len(state.sessions)
        with self.assertRaises(HTTPException):
            asyncio.run(routes.start_serial_sniff(SerialSniffRequest(port=port, duration=1.0)))
        self.assertEqual(len(state.sessions), before)

    def test_launch_releases_resource_and_abort_state_when_task_ends(self):
        key = resource_guard.serial_resource("/dev/ttyUSB-done")

        async def _run():
            async def _work():
                return None

            result = routes._launch_scan(
                _work, session_id="sess-done", resource=key, label="Prova"
            )
            self.assertEqual(result["status"], "started")
            self.assertIsNotNone(resource_guard.claim_for(key))
            # Lascia completare il task e i suoi done-callback.
            for _ in range(20):
                await asyncio.sleep(0)
                if resource_guard.claim_for(key) is None:
                    break

        asyncio.run(_run())
        self.assertIsNone(resource_guard.claim_for(key), "la risorsa va liberata al termine")


class TestSessionRetention(unittest.TestCase):
    """Lo storico scansioni non deve crescere senza limiti."""

    def _state_with_cap(self, cap: int) -> AppState:
        st = AppState()
        st.max_sessions = cap
        return st

    def test_finished_sessions_are_capped(self):
        st = self._state_with_cap(5)
        for _ in range(20):
            session = st.new_session(Protocol.MODBUS_RTU, {})
            st.finish_session(session.id)
        self.assertLessEqual(len(st.sessions), 5)

    def test_running_sessions_are_never_discarded(self):
        st = self._state_with_cap(3)
        running = [st.new_session(Protocol.MODBUS_RTU, {}).id for _ in range(4)]
        for _ in range(20):
            session = st.new_session(Protocol.MODBUS_TCP, {})
            st.finish_session(session.id)
        for session_id in running:
            with self.subTest(session=session_id):
                self.assertIn(session_id, st.sessions)

    def test_snapshot_is_bounded_by_the_cap(self):
        st = self._state_with_cap(4)
        for _ in range(30):
            session = st.new_session(Protocol.KNX_IP, {})
            st.finish_session(session.id)
        self.assertLessEqual(len(st.snapshot()["sessions"]), 4)

    def test_clear_drops_finished_sessions_but_keeps_running_ones(self):
        st = self._state_with_cap(50)
        done = st.new_session(Protocol.MODBUS_RTU, {})
        st.finish_session(done.id)
        live = st.new_session(Protocol.MODBUS_RTU, {})
        st.clear()
        self.assertNotIn(done.id, st.sessions)
        self.assertIn(live.id, st.sessions)

    def test_finish_session_marks_status_and_timestamp(self):
        st = self._state_with_cap(50)
        session = st.new_session(Protocol.BACNET_IP, {})
        st.finish_session(session.id, ScanStatus.ERROR)
        stored = st.sessions[session.id]
        self.assertEqual(stored.status, ScanStatus.ERROR)
        self.assertIsNotNone(stored.finished_at)


if __name__ == "__main__":
    unittest.main()
