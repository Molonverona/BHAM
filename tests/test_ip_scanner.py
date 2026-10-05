"""
BHAM – Unit tests for BACS IP Scanner, OUI IEEE database and network endpoints.
Runs cleanly with standard Python unittest and -W error.
"""

from __future__ import annotations

import asyncio
import unittest

from api import routes
from api.schemas import IPScanRequest
from core.oui_lookup import format_mac_colon, get_vendor_by_mac, normalize_mac
from core.simulator import simulator
from data.models import IPHost, Protocol, ScanStatus
from data.state import state
from scanners.ip_scanner import (
    BACS_PORT_SERVICES,
    IPScanner,
    parse_target_ips,
    read_os_arp_table,
)


class TestOUILookup(unittest.TestCase):
    def test_vendor_known_prefixes(self):
        # Siemens
        self.assertEqual(get_vendor_by_mac("00:1c:06:12:34:56"), "Siemens AG")
        # Schneider
        self.assertIn("Schneider", get_vendor_by_mac("00:80:f4:aa:bb:cc"))
        # Carel
        self.assertEqual(get_vendor_by_mac("00:04:cd:01:02:03"), "Carel Industries S.p.A.")
        # WAGO
        self.assertEqual(get_vendor_by_mac("00:30:de:11:22:33"), "WAGO Kontakttechnik GmbH")
        # Beckhoff
        self.assertEqual(get_vendor_by_mac("00:01:05:44:55:66"), "Beckhoff Automation GmbH")
        # Moxa
        self.assertEqual(get_vendor_by_mac("00:90:e8:77:88:99"), "Moxa Inc.")
        # Tridium JACE
        self.assertEqual(get_vendor_by_mac("00:50:f1:00:11:22"), "Tridium Inc. (JACE)")
        # Belimo
        self.assertEqual(get_vendor_by_mac("00:1c:d2:33:44:55"), "Belimo Automation AG")

    def test_vendor_various_formats(self):
        # Hyphens
        self.assertEqual(get_vendor_by_mac("00-1C-06-AA-BB-CC"), "Siemens AG")
        # Cisco dot notation
        self.assertEqual(get_vendor_by_mac("001c.06aa.bbcc"), "Siemens AG")
        # Prefix only 6 hex chars
        self.assertEqual(get_vendor_by_mac("001C06"), "Siemens AG")

    def test_vendor_unknown_or_invalid(self):
        self.assertIsNone(get_vendor_by_mac(""))
        self.assertIsNone(get_vendor_by_mac("00"))
        self.assertIsNone(get_vendor_by_mac("FF:FF:FF:FF:FF:FF"))

    def test_mac_normalization(self):
        self.assertEqual(normalize_mac("00:1c:06:12:34:56"), "001C06123456")
        self.assertEqual(normalize_mac("00-1c-06-12-34-56"), "001C06123456")
        self.assertEqual(format_mac_colon("001c06123456"), "00:1C:06:12:34:56")
        self.assertEqual(format_mac_colon("00:1c:06:12:34:56"), "00:1C:06:12:34:56")


class TestTargetIPParsing(unittest.TestCase):
    def test_parse_single_ip(self):
        ips = parse_target_ips("192.168.1.50")
        self.assertEqual(ips, ["192.168.1.50"])

    def test_parse_range_full(self):
        ips = parse_target_ips("192.168.1.1 - 192.168.1.5")
        self.assertEqual(
            ips,
            [
                "192.168.1.1",
                "192.168.1.2",
                "192.168.1.3",
                "192.168.1.4",
                "192.168.1.5",
            ],
        )

    def test_parse_range_compact(self):
        ips = parse_target_ips("10.0.0.8-12")
        self.assertEqual(
            ips,
            [
                "10.0.0.8",
                "10.0.0.9",
                "10.0.0.10",
                "10.0.0.11",
                "10.0.0.12",
            ],
        )

    def test_parse_cidr(self):
        ips = parse_target_ips("192.168.10.0/30")
        self.assertEqual(ips, ["192.168.10.1", "192.168.10.2"])

    def test_parse_invalid(self):
        self.assertEqual(parse_target_ips(""), [])
        self.assertEqual(parse_target_ips("not.an.ip.address"), [])


class TestIPScanner(unittest.TestCase):
    def setUp(self):
        state.clear()

    def tearDown(self):
        state.clear()

    def test_ip_scanner_empty_target(self):
        session = state.new_session(Protocol.UNKNOWN, {})
        scanner = IPScanner(session_id=session.id)
        req = IPScanRequest(subnet="")
        asyncio.run(scanner.scan(req))

        s = state.sessions.get(session.id)
        self.assertIsNotNone(s)
        self.assertEqual(s.status, ScanStatus.ERROR)
        self.assertIn("Nessun indirizzo IP valido", s.error_message or "")

    def test_ip_scanner_single_ip_scan(self):
        session = state.new_session(Protocol.UNKNOWN, {})
        scanner = IPScanner(session_id=session.id)
        req = IPScanRequest(
            subnet="127.0.0.1",
            ports=[502, 80],
            ping_timeout_ms=50,
            port_timeout_ms=50,
            resolve_names=False,
            concurrency=2,
        )
        asyncio.run(scanner.scan(req))

        s = state.sessions.get(session.id)
        self.assertIsNotNone(s)
        self.assertEqual(s.status, ScanStatus.COMPLETED)
        self.assertEqual(s.progress_pct, 100.0)

    def test_ip_scanner_abort(self):
        from scanners.base import abort_session
        session = state.new_session(Protocol.UNKNOWN, {})
        scanner = IPScanner(session_id=session.id)
        scanner.reset_abort()
        abort_session(session.id)
        self.assertTrue(scanner.is_aborted())

        req = IPScanRequest(
            subnet="192.168.99.1-10",
            ports=[502],
            ping_timeout_ms=50,
            port_timeout_ms=50,
            resolve_names=False,
        )
        asyncio.run(scanner.scan(req))
        s = state.sessions.get(session.id)
        self.assertIsNotNone(s)
        self.assertEqual(s.status, ScanStatus.ABORTED)

    def test_read_os_arp_table(self):
        table = read_os_arp_table()
        self.assertIsInstance(table, dict)


class TestIPScannerAPI(unittest.TestCase):
    def setUp(self):
        state.clear()

    def tearDown(self):
        state.clear()

    def test_api_oui_lookup_endpoint(self):
        res = asyncio.run(routes.lookup_oui("00:1C:06:12:34:56"))
        self.assertTrue(res["recognized"])
        self.assertEqual(res["vendor"], "Siemens AG")
        self.assertEqual(res["mac"], "00:1C:06:12:34:56")

        res_un = asyncio.run(routes.lookup_oui("11:22:33:44:55:66"))
        self.assertFalse(res_un["recognized"])
        self.assertIsNone(res_un["vendor"])

    def test_api_start_ip_scan(self):
        req = IPScanRequest(subnet="127.0.0.1", ports=[502], ping_timeout_ms=50, port_timeout_ms=50)
        res = asyncio.run(routes.start_ip_scan(req))
        self.assertIn("session_id", res)
        self.assertEqual(res["status"], "started")


class TestSimulatorIPEnrichment(unittest.TestCase):
    def setUp(self):
        state.clear()

    def tearDown(self):
        asyncio.run(simulator.stop())
        state.clear()

    def test_simulator_populated_with_vendors_and_services(self):
        asyncio.run(simulator.start())
        hosts = list(state.ip_hosts.values())
        self.assertGreaterEqual(len(hosts), 5)

        # Trova host Siemens S7-1200
        siemens = next((h for h in hosts if h.ip == "192.168.1.10"), None)
        self.assertIsNotNone(siemens)
        self.assertEqual(siemens.vendor, "Siemens AG")
        self.assertEqual(siemens.hostname, "plc-simatic-s7-1200")
        self.assertIn(502, siemens.open_ports)
        self.assertIn(47808, siemens.open_ports)
        self.assertEqual(siemens.services.get(502), "Modbus TCP")

        # Trova host JACE Tridium
        jace = next((h for h in hosts if h.ip == "192.168.1.20"), None)
        self.assertIsNotNone(jace)
        self.assertEqual(jace.vendor, "Tridium Inc. (JACE)")
        self.assertIn(1911, jace.open_ports)


if __name__ == "__main__":
    unittest.main()
