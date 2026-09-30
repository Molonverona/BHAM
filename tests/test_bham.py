"""
BHAM – Comprehensive Test Suite
Tests models, app state, session store, maps manager, reporting, and REST API routes directly.
Runs cleanly with standard Python unittest and -W error.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from api import routes
from core.session_store import delete_session, list_sessions, load_session, save_session
from data.maps_manager import MapEntry, MapsManager
from data.models import (
    BACnetDevice,
    IPHost,
    KNXDevice,
    ModbusDevice,
    Parity,
    Protocol,
    ScanStatus,
    SerialParams,
    SessionConfig,
    utc_now,
)
from data.state import AppState, state
from reports.excel import generate_excel
from reports.pdf import generate_pdf
from scanners.bacnet import parse_bacnet_ports, port_label
from scanners.modbus import parse_modbus_tcp_ports


class TestModels(unittest.TestCase):
    def test_utc_now_timezone_aware(self):
        now = utc_now()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.tzinfo, timezone.utc)

    def test_modbus_device_serialization(self):
        dev = ModbusDevice(
            slave_id=1,
            protocol=Protocol.MODBUS_RTU,
            serial_params=SerialParams(port="/dev/ttyUSB0", baudrate=9600, parity=Parity.NONE),
            response_time_ms=18.4,
        )
        data = dev.model_dump(mode="json")
        self.assertEqual(data["slave_id"], 1)
        self.assertEqual(data["protocol"], "modbus_rtu")
        self.assertEqual(data["serial_params"]["port"], "/dev/ttyUSB0")

    def test_knx_device_model(self):
        dev = KNXDevice(
            individual_address="1.1.0",
            device_name="Test KNX Router",
            serial_number="00C101234567",
            mac_address="00:0c:29:ab:cd:ef",
            ip_address="192.168.1.200",
            medium="TP1",
        )
        self.assertEqual(dev.individual_address, "1.1.0")
        self.assertEqual(dev.medium, "TP1")
        data = dev.model_dump(mode="json")
        self.assertEqual(data["ip_address"], "192.168.1.200")


class TestStateAndSnapshot(unittest.TestCase):
    def setUp(self):
        self.app_state = AppState()

    def test_upsert_and_snapshot(self):
        mb = ModbusDevice(slave_id=5, protocol=Protocol.MODBUS_TCP, ip="192.168.1.10")
        bn = BACnetDevice(device_id=1234, address="192.168.1.20", vendor_name="Johnson Controls")
        kx = KNXDevice(individual_address="1.2.3", ip_address="192.168.1.30", device_name="Gira Gateway")
        host = IPHost(ip="192.168.1.50", mac="00:1c:06:11:22:33", hostname="plc-station")

        self.app_state.upsert_modbus(mb)
        self.app_state.upsert_bacnet(bn)
        self.app_state.upsert_knx(kx)
        self.app_state.upsert_ip_host(host)

        snap = self.app_state.snapshot()
        self.assertEqual(len(snap["modbus_devices"]), 1)
        self.assertEqual(len(snap["bacnet_devices"]), 1)
        self.assertEqual(len(snap["knx_devices"]), 1)
        self.assertEqual(len(snap["ip_hosts"]), 1)

    def test_restore_snapshot(self):
        snap = {
            "session_config": {
                "site_name": "Test Plant A",
                "serial_port": "/dev/ttyUSB1",
                "serial_baudrate": 19200,
                "serial_parity": "E",
                "serial_stopbits": 1,
            },
            "modbus_devices": [{"slave_id": 10, "protocol": "modbus_rtu"}],
            "bacnet_devices": [{"device_id": 888, "address": "192.168.1.88"}],
            "knx_devices": [{"individual_address": "1.1.1", "ip_address": "192.168.1.99"}],
            "ip_hosts": [{"ip": "192.168.1.101"}],
        }

        self.app_state.restore_snapshot(snap)
        self.assertIsNotNone(self.app_state.session_config)
        self.assertEqual(self.app_state.session_config.site_name, "Test Plant A")
        self.assertEqual(len(self.app_state.modbus_devices), 1)
        self.assertEqual(len(self.app_state.bacnet_devices), 1)
        self.assertEqual(len(self.app_state.knx_devices), 1)
        self.assertEqual(len(self.app_state.ip_hosts), 1)

    def test_clear_state(self):
        self.app_state.upsert_modbus(ModbusDevice(slave_id=1))
        self.app_state.clear()
        self.assertEqual(len(self.app_state.modbus_devices), 0)

    def test_get_topology(self):
        cfg = SessionConfig(
            site_name="Topologia Ospedale",
            serial_port="/dev/ttyUSB0",
            serial_baudrate=19200,
            serial_parity=Parity.EVEN,
            serial_stopbits=1,
            scan_iface="eth0",
            scan_ip="192.168.1.100/24",
        )
        self.app_state.set_session_config(cfg)
        self.app_state.upsert_modbus(ModbusDevice(
            slave_id=1,
            protocol=Protocol.MODBUS_RTU,
            serial_params=SerialParams(port="/dev/ttyUSB0", baudrate=19200, parity=Parity.EVEN),
            response_time_ms=25.0,
        ))
        self.app_state.upsert_modbus(ModbusDevice(
            slave_id=2,
            protocol=Protocol.MODBUS_TCP,
            ip="192.168.1.50",
            tcp_port=502,
        ))
        self.app_state.upsert_bacnet(BACnetDevice(
            device_id=5001,
            address="192.168.1.60",
            vendor_name="Trane",
            model_name="Chiller-RTAF",
        ))
        self.app_state.upsert_knx(KNXDevice(
            individual_address="1.1.20",
            ip_address="192.168.1.70",
            device_name="ABB KNX IP Router",
        ))
        self.app_state.upsert_ip_host(IPHost(
            ip="192.168.1.1",
            mac="00:11:22:33:44:55",
            hostname="gateway-main",
        ))

        topo = self.app_state.get_topology()
        self.assertEqual(topo["root_id"], "node:host")
        self.assertGreaterEqual(len(topo["nodes"]), 6)
        self.assertGreaterEqual(len(topo["links"]), 5)

        # Check nodes existence
        node_ids = {n["id"] for n in topo["nodes"]}
        self.assertIn("node:host", node_ids)
        self.assertIn("node:iface:serial", node_ids)
        self.assertIn("node:iface:nic", node_ids)
        self.assertIn("node:bus:modbus_rtu", node_ids)
        self.assertIn("node:bus:modbus_tcp", node_ids)
        self.assertIn("node:bus:bacnet_ip", node_ids)
        self.assertIn("node:bus:knx_ip", node_ids)
        self.assertIn("node:bus:arp", node_ids)
        self.assertIn("node:dev:modbus:rtu:1", node_ids)
        self.assertIn("node:dev:bacnet:ip:5001", node_ids)
        self.assertIn("node:dev:knx:1.1.20", node_ids)

        # Check root label
        host_node = next(n for n in topo["nodes"] if n["id"] == "node:host")
        self.assertEqual(host_node["label"], "Topologia Ospedale")


class TestSessionStore(unittest.TestCase):
    def test_save_load_list_and_delete(self):
        test_snap = {
            "modbus_devices": [{"slave_id": 1}],
            "bacnet_devices": [{"device_id": 100}],
            "knx_devices": [{"individual_address": "1.1.0", "ip_address": "192.168.1.10"}],
            "ip_hosts": [{"ip": "192.168.1.2"}],
        }
        saved_path = save_session("UnitTest Site", {}, test_snap)
        self.assertTrue(saved_path.exists())

        # List sessions
        sessions = list_sessions()
        found = next((s for s in sessions if s["filename"] == saved_path.name), None)
        self.assertIsNotNone(found)
        self.assertEqual(found["device_counts"]["modbus"], 1)
        self.assertEqual(found["device_counts"]["bacnet"], 1)
        self.assertEqual(found["device_counts"]["knx"], 1)
        self.assertEqual(found["device_counts"]["ip_hosts"], 1)

        # Load session
        loaded = load_session(saved_path.name)
        self.assertEqual(loaded["name"], "UnitTest Site")
        self.assertEqual(len(loaded["results"]["knx_devices"]), 1)

        # Delete session
        delete_session(saved_path.name)
        self.assertFalse(saved_path.exists())


class TestMapsManager(unittest.TestCase):
    def test_import_and_export(self):
        mgr = MapsManager()
        data = [
            {"slave_id": 1, "register": 100, "label": "Temp Out", "unit": "°C", "scale": 0.1},
            {"slave_id": 1, "register": 101, "label": "Pressure", "unit": "bar", "scale": 0.01},
            {"slave_id": 2, "register": 200, "label": "Status Word", "type": "input"},
        ]
        count = mgr.import_from_json(data)
        self.assertEqual(count, 3)

        map1 = mgr.get_map(1)
        self.assertEqual(len(map1), 2)
        self.assertEqual(map1[0].register, 100)
        self.assertEqual(map1[0].unit, "°C")

        map2 = mgr.get_map(2)
        self.assertEqual(len(map2), 1)
        self.assertEqual(map2[0].register_type, "input")

        exp = mgr.export_to_json()
        self.assertEqual(exp["total_points"], 3)
        self.assertEqual(len(exp["devices"]), 2)
        self.assertEqual(exp["devices"][0]["slave_id"], 1)


class TestReporting(unittest.TestCase):
    def setUp(self):
        state.clear()
        state.upsert_modbus(ModbusDevice(
            slave_id=1,
            protocol=Protocol.MODBUS_RTU,
            response_time_ms=12.5,
            registers={"40001": {"hex": "0x00E4", "int16": 228, "dec": 228, "float32": "", "description": "Temp Mandata"}},
        ))
        state.upsert_bacnet(BACnetDevice(
            device_id=101,
            address="192.168.1.5",
            vendor_name="WAGO",
            object_list=[{"object_identifier": "analog-input:1", "object_type": "analogInput", "object_name": "T_Esterna", "present_value": 18.2, "units": "°C"}],
        ))
        state.upsert_knx(KNXDevice(individual_address="1.1.0", ip_address="192.168.1.8", device_name="Router"))
        state.upsert_ip_host(IPHost(ip="192.168.1.1", mac="00:1c:06:aa:bb:cc"))

    def test_excel_generation(self):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
            path = tf.name
        try:
            generate_excel(path)
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 1000)

            # Verifica presenza di tutti i fogli arricchiti v2.0
            import openpyxl
            wb = openpyxl.load_workbook(path)
            expected_sheets = [
                "Network Topology", "Modbus Devices", "BACnet Devices",
                "KNX Devices", "IP Hosts", "Modbus Registers",
                "BACnet Objects", "Report Info"
            ]
            for s in expected_sheets:
                self.assertIn(s, wb.sheetnames)
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_pdf_generation(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
            path = tf.name
        try:
            generate_pdf(path)
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 1000)
        finally:
            if os.path.exists(path):
                os.unlink(path)



class TestApiRoutes(unittest.TestCase):
    def test_health_endpoint(self):
        res = asyncio.run(routes.health())
        self.assertEqual(res["status"], "ok")

    def test_state_endpoints(self):
        res = asyncio.run(routes.get_state())
        self.assertIn("modbus_devices", res)

        del_res = asyncio.run(routes.clear_state())
        self.assertTrue(del_res["cleared"])

    def test_setup_endpoints(self):
        cfg_res = asyncio.run(routes.get_config())
        self.assertIn("configured", cfg_res)

        post_res = asyncio.run(routes.configure_session(routes.ConfigureRequest(
            site_name="Test Site 123",
            serial_port="/dev/ttyUSB0",
            serial_baudrate=9600,
            serial_parity="N",
            serial_stopbits=1,
            scan_iface="eth0",
            single_iface_mode=True,
        )))
        self.assertTrue(post_res["configured"])

    def test_saved_sessions_and_restore(self):
        save_res = asyncio.run(routes.save_current_session(routes.SaveSessionRequest(name="ApiTestSession")))
        self.assertTrue(save_res["saved"])
        filename = save_res["filename"]

        list_res = asyncio.run(routes.list_saved_sessions())
        self.assertTrue(any(s["filename"] == filename for s in list_res))

        rest_res = asyncio.run(routes.restore_saved_session(filename))
        self.assertTrue(rest_res["restored"])

        del_res = asyncio.run(routes.delete_saved_session(filename))
        self.assertTrue(del_res["deleted"])

    def test_abort_scan(self):
        async def _test():
            # Create a dummy session to abort
            tcp_req = routes.ModbusTCPScanRequest(hosts=["127.0.0.1"])
            res = await routes.start_modbus_tcp(tcp_req)
            session_id = res["session_id"]

            # Now abort it
            abort_res = await routes.abort_scan(session_id)
            self.assertTrue(abort_res["aborted"])

        asyncio.run(_test())


class TestCustomPorts(unittest.TestCase):
    def test_bacnet_port_parsing(self):
        # Basic int
        self.assertEqual(parse_bacnet_ports(47808), [47808])
        # Default / None
        self.assertEqual(parse_bacnet_ports(None), [47808])
        # Symbolic BAC0 -> BACF
        self.assertEqual(parse_bacnet_ports("BAC0"), [47808])
        self.assertEqual(parse_bacnet_ports("BAC1"), [47809])
        self.assertEqual(parse_bacnet_ports("BACF"), [47823])
        # Hex notation
        self.assertEqual(parse_bacnet_ports("0xBAC0"), [47808])
        # Parenthesized label (from UI presets)
        self.assertEqual(parse_bacnet_ports("BAC0 (47808)"), [47808])
        # Ranges
        self.assertEqual(parse_bacnet_ports("BAC0..BAC3"), [47808, 47809, 47810, 47811])
        self.assertEqual(parse_bacnet_ports("47808-47810"), [47808, 47809, 47810])
        # Multi token & custom ports
        self.assertEqual(parse_bacnet_ports("BAC0, BAC1, 50000"), [47808, 47809, 50000])

    def test_bacnet_port_labels(self):
        self.assertEqual(port_label(47808), "BAC0 (47808)")
        self.assertEqual(port_label(47809), "BAC1 (47809)")
        self.assertEqual(port_label(47823), "BACF (47823)")
        self.assertEqual(port_label(50000), "50000")

    def test_modbus_tcp_port_parsing(self):
        self.assertEqual(parse_modbus_tcp_ports(None), [502])
        self.assertEqual(parse_modbus_tcp_ports(502), [502])
        self.assertEqual(parse_modbus_tcp_ports("5020"), [5020])
        self.assertEqual(parse_modbus_tcp_ports("502, 503, 5020"), [502, 503, 5020])
        self.assertEqual(parse_modbus_tcp_ports("502-504"), [502, 503, 504])
        self.assertEqual(parse_modbus_tcp_ports([502, 503]), [502, 503])

    def test_scan_trigger_models_and_endpoints(self):
        async def _test():
            # Modbus TCP with custom ports
            tcp_req = routes.ModbusTCPScanRequest(hosts=["127.0.0.1"], tcp_port="502, 503")
            res_tcp = await routes.start_modbus_tcp(tcp_req)
            self.assertEqual(res_tcp["status"], "started")
            self.assertIn(res_tcp["session_id"], state.sessions)

            # BACnet with BAC0..BAC2
            bac_req = routes.BACnetIPScanRequest(iface="", port="BAC0..BAC2")
            res_bac = await routes.start_bacnet_ip(bac_req)
            self.assertEqual(res_bac["status"], "started")
            self.assertIn(res_bac["session_id"], state.sessions)

            # KNX with custom port
            knx_req = routes.KNXIPScanRequest(iface="", port=3672, timeout=0.1)
            res_knx = await routes.start_knx_ip(knx_req)
            self.assertEqual(res_knx["status"], "started")
            self.assertIn(res_knx["session_id"], state.sessions)

            # Abort to let any spawned background coroutines terminate cleanly
            await routes.abort_scan(res_knx["session_id"])
            await asyncio.sleep(0.05)

        asyncio.run(_test())


class TestSerialSniffer(unittest.TestCase):
    def setUp(self):
        state.clear()

    def test_modbus_rtu_frame_dissection(self):
        from scanners.serial_sniffer import (
            calc_modbus_crc,
            check_modbus_crc,
            SerialSniffer,
        )
        from data.models import FrameDirection

        sniffer = SerialSniffer(session_id="test-session-sniff")

        # 1. Query FC03 (Master -> Slave 1, addr 100, count 2)
        q_raw = bytes([1, 3, 0, 100, 0, 2])
        q_crc = calc_modbus_crc(q_raw)
        q_frame = q_raw + bytes([q_crc & 0xFF, (q_crc >> 8) & 0xFF])
        self.assertTrue(check_modbus_crc(q_frame))

        active_nodes: set[int] = set()
        dissected_q = sniffer._dissect_modbus_frame(
            q_frame, "/dev/ttyUSB0", 9600, "N", 1, active_nodes
        )
        self.assertEqual(dissected_q.direction, FrameDirection.MASTER_TO_SLAVE)
        self.assertEqual(dissected_q.source_addr, "Master")
        self.assertEqual(dissected_q.dest_addr, "1")
        self.assertEqual(dissected_q.function_code, 3)
        self.assertEqual(dissected_q.data["start_addr"], 100)
        self.assertEqual(dissected_q.data["count"], 2)
        self.assertIn(1, active_nodes)

        # 2. Response FC03 (Slave 1 -> Master, 2 regs: 1234, 5678)
        r_raw = bytes([1, 3, 4, 0x04, 0xD2, 0x16, 0x2E])
        r_crc = calc_modbus_crc(r_raw)
        r_frame = r_raw + bytes([r_crc & 0xFF, (r_crc >> 8) & 0xFF])
        self.assertTrue(check_modbus_crc(r_frame))

        dissected_r = sniffer._dissect_modbus_frame(
            r_frame, "/dev/ttyUSB0", 9600, "N", 1, active_nodes
        )
        self.assertEqual(dissected_r.direction, FrameDirection.SLAVE_TO_MASTER)
        self.assertEqual(dissected_r.source_addr, "1")
        self.assertEqual(dissected_r.dest_addr, "Master")
        self.assertEqual(dissected_r.function_code, 3)
        self.assertEqual(dissected_r.data["registers"], [1234, 5678])

        # Verifica inserimento automatico nel catalogo Modbus
        self.assertIn("/dev/ttyUSB0-1", state.modbus_devices)
        dev = state.modbus_devices["/dev/ttyUSB0-1"]
        self.assertIn("sniffed", dev.tags)
        self.assertEqual(dev.registers["reg_0"], 1234)
        self.assertEqual(dev.registers["reg_1"], 5678)

    def test_bacnet_mstp_frame_dissection(self):
        # Note: This test generates frames using the same CRC functions it tests,
        # so it verifies internal consistency, not ASHRAE 135 standard compliance.
        # For full compliance testing, external reference vectors are needed.
        from scanners.serial_sniffer import (
            calc_mstp_header_crc,
            check_mstp_header_crc,
            calc_mstp_data_crc,
            check_mstp_data_crc,
            SerialSniffer,
        )
        from data.models import FrameDirection

        sniffer = SerialSniffer(session_id="test-session-mstp")

        # 1. Token Frame: Type 0, Dest MAC 5, Src MAC 2, Len 0
        h_bytes = bytes([0, 5, 2, 0, 0])
        c = 0xFF
        for b in h_bytes:
            c = calc_mstp_header_crc(b, c)
        h_crc = (~c) & 0xFF
        token_frame = bytes([0x55, 0xFF]) + h_bytes + bytes([h_crc])

        active_nodes: set[int] = set()
        buf = bytearray(token_frame)
        parsed = sniffer._parse_mstp_frame(buf, "/dev/ttyUSB0", active_nodes)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        frame, consumed, is_valid = parsed
        self.assertTrue(is_valid)
        self.assertEqual(consumed, 8)
        self.assertEqual(frame.direction, FrameDirection.TOKEN)
        self.assertEqual(frame.source_addr, "2")
        self.assertEqual(frame.dest_addr, "5")
        self.assertIn(2, active_nodes)
        self.assertIn(5, active_nodes)

        # Verifica inserimento automatico nel catalogo BACnet
        self.assertIn(2, state.bacnet_devices)
        bdev = state.bacnet_devices[2]
        self.assertEqual(bdev.protocol, Protocol.BACNET_MSTP)
        self.assertIn("sniffed", bdev.tags)

        # 2. Data Frame con CRC16
        data_payload = b"BHAM Test MS-TP Payload"
        data_len = len(data_payload)
        d_header = bytes([5, 10, 2, (data_len >> 8) & 0xFF, data_len & 0xFF])
        c = 0xFF
        for b in d_header:
            c = calc_mstp_header_crc(b, c)
        d_header_crc = (~c) & 0xFF
        d_crc16 = calc_mstp_data_crc(data_payload)
        full_data_frame = (
            bytes([0x55, 0xFF])
            + d_header
            + bytes([d_header_crc])
            + data_payload
            + bytes([d_crc16 & 0xFF, (d_crc16 >> 8) & 0xFF])
        )

        buf2 = bytearray(full_data_frame)
        parsed_data = sniffer._parse_mstp_frame(buf2, "/dev/ttyUSB0", active_nodes)
        self.assertIsNotNone(parsed_data)
        assert parsed_data is not None
        d_frame, d_consumed, d_is_valid = parsed_data
        self.assertTrue(d_is_valid)
        self.assertEqual(d_consumed, len(full_data_frame))
        self.assertEqual(d_frame.data["data_len"], data_len)

    def test_serial_sniff_endpoint_and_health(self):
        async def _test():
            req = routes.SerialSniffRequest(
                port="/dev/null",
                baudrate=9600,
                duration=0.1,
            )
            res = await routes.start_serial_sniff(req)
            self.assertEqual(res["status"], "started")
            self.assertIn(res["session_id"], state.sessions)

            # Legge bus health (puo essere None se non ancora calcolato)
            _ = await routes.get_serial_bus_health()

            await routes.abort_scan(res["session_id"])
            await asyncio.sleep(0.05)

        asyncio.run(_test())

    def test_modbus_smart_scan_endpoint(self):
        async def _test():
            req = routes.ModbusSmartScanBody(
                slave_id=1,
                protocol="tcp",
                ip="127.0.0.1",
                tcp_port=502,
            )
            res = await routes.modbus_smart_scan(req)
            self.assertEqual(res["slave_id"], 1)
            self.assertIn("registers", res)

        asyncio.run(_test())

    def test_bacnet_objects_endpoint(self):
        async def _test():
            res = await routes.get_bacnet_objects(device_id=1234, address="127.0.0.1:47808")
            self.assertEqual(res["device_id"], 1234)
            self.assertIn("objects", res)

        asyncio.run(_test())

    def test_topology_endpoint(self):
        async def _test():
            res = await routes.get_topology()
            self.assertIn("root_id", res)
            self.assertIn("nodes", res)
            self.assertIn("links", res)
            self.assertIn("summary", res)

        asyncio.run(_test())


class TestSessionDiff(unittest.TestCase):
    """Test suite per il modulo core/session_diff.py ed endpoint /sessions/diff."""

    def test_compare_snapshots_full(self):
        from core.session_diff import compare_snapshots
        from data.models import DiffStatus

        base_snap = {
            "modbus_devices": [
                {
                    "slave_id": 1,
                    "protocol": "modbus_rtu",
                    "serial_params": {"port": "/dev/ttyUSB0", "baudrate": 9600, "parity": "N", "stopbits": 1},
                    "registers": {"40001": 215},
                    "response_time_ms": 35.0,
                },
                {
                    "slave_id": 5,
                    "protocol": "modbus_rtu",
                    "serial_params": {"port": "/dev/ttyUSB0", "baudrate": 9600, "parity": "N", "stopbits": 1},
                },
            ],
            "bacnet_devices": [
                {
                    "device_id": 100,
                    "address": "192.168.1.50",
                    "vendor_name": "Siemens",
                    "model_name": "PXC001",
                    "firmware_revision": "1.0",
                }
            ],
            "knx_devices": [
                {
                    "individual_address": "1.1.0",
                    "ip_address": "192.168.1.200",
                    "device_name": "KNX IP Router",
                    "medium": "TP1",
                }
            ],
            "ip_hosts": [
                {
                    "ip": "192.168.1.10",
                    "mac": "AA:BB:CC:DD:EE:01",
                    "hostname": "controller-1",
                    "open_ports": [80, 502],
                }
            ],
        }

        target_snap = {
            "modbus_devices": [
                # Modbus 1: modificato baudrate e latenza
                {
                    "slave_id": 1,
                    "protocol": "modbus_rtu",
                    "serial_params": {"port": "/dev/ttyUSB0", "baudrate": 19200, "parity": "N", "stopbits": 1},
                    "registers": {"40001": 215},
                    "response_time_ms": 320.0,
                },
                # Modbus 2: nuovo apparato
                {
                    "slave_id": 2,
                    "protocol": "modbus_rtu",
                    "serial_params": {"port": "/dev/ttyUSB0", "baudrate": 19200, "parity": "N", "stopbits": 1},
                },
                # Modbus 5: rimosso (non presente in target)
            ],
            "bacnet_devices": [
                # BACnet 100: modificato indirizzo e firmware
                {
                    "device_id": 100,
                    "address": "192.168.1.55",
                    "vendor_name": "Siemens",
                    "model_name": "PXC001",
                    "firmware_revision": "2.0",
                },
                # BACnet 200: nuovo apparato
                {
                    "device_id": 200,
                    "address": "192.168.1.60",
                    "vendor_name": "Carel",
                    "model_name": "pCO5",
                },
            ],
            "knx_devices": [
                # KNX 1.1.0: invariato
                {
                    "individual_address": "1.1.0",
                    "ip_address": "192.168.1.200",
                    "device_name": "KNX IP Router",
                    "medium": "TP1",
                },
                # KNX 1.1.5: nuovo apparato
                {
                    "individual_address": "1.1.5",
                    "ip_address": "192.168.1.205",
                    "device_name": "KNX Actuator",
                    "medium": "TP1",
                },
            ],
            "ip_hosts": [
                # Host MAC AA:BB:CC:DD:EE:01: IP riassegnato da .10 a .15
                {
                    "ip": "192.168.1.15",
                    "mac": "AA:BB:CC:DD:EE:01",
                    "hostname": "controller-1",
                    "open_ports": [80, 502, 47808],
                },
                # Nuovo host
                {
                    "ip": "192.168.1.99",
                    "mac": "11:22:33:44:55:66",
                    "hostname": "printer",
                },
            ],
        }

        diff = compare_snapshots(base_snap, target_snap, "Collaudo 2026-09-01", "Collaudo 2026-09-29")
        self.assertEqual(diff.baseline_name, "Collaudo 2026-09-01")
        self.assertEqual(diff.target_name, "Collaudo 2026-09-29")

        # Modbus: 1 modificato, 1 aggiunto, 1 rimosso
        mb_sum = diff.summary["modbus"]
        self.assertEqual(mb_sum.added, 1)
        self.assertEqual(mb_sum.removed, 1)
        self.assertEqual(mb_sum.modified, 1)
        self.assertEqual(mb_sum.unchanged, 0)

        # BACnet: 1 modificato, 1 aggiunto, 0 rimossi
        bn_sum = diff.summary["bacnet"]
        self.assertEqual(bn_sum.added, 1)
        self.assertEqual(bn_sum.removed, 0)
        self.assertEqual(bn_sum.modified, 1)

        # KNX: 1 invariato, 1 aggiunto
        knx_sum = diff.summary["knx"]
        self.assertEqual(knx_sum.added, 1)
        self.assertEqual(knx_sum.unchanged, 1)

        # IP Host: 1 modificato (stesso MAC con nuovo IP), 1 aggiunto
        host_sum = diff.summary["ip_host"]
        self.assertEqual(host_sum.modified, 1)
        self.assertEqual(host_sum.added, 1)

        # Totali aggregati
        tot = diff.summary["total"]
        self.assertEqual(tot.added, 4)      # Modbus 2, BACnet 200, KNX 1.1.5, Host .99
        self.assertEqual(tot.removed, 1)    # Modbus 5
        self.assertEqual(tot.modified, 3)   # Modbus 1, BACnet 100, Host MAC ...01
        self.assertEqual(tot.unchanged, 1)  # KNX 1.1.0

        # Verifica dettagli modifiche su Modbus 1
        mb1 = next(it for it in diff.items if it.identifier == "RTU Slave #1")
        self.assertEqual(mb1.status, DiffStatus.MODIFIED)
        changed_fields = {c.field for c in mb1.changes}
        self.assertIn("serial_baudrate", changed_fields)
        self.assertIn("response_time_ms", changed_fields)

    def test_diff_sessions_api_endpoint(self):
        from core.session_store import save_session, delete_session
        from data.models import ModbusDevice, BACnetDevice, Protocol, SessionDiffRequest

        # 1. Salva una sessione baseline fittizia
        base_state = {
            "modbus_devices": [
                {"slave_id": 10, "protocol": "modbus_rtu", "response_time_ms": 25.0}
            ],
            "bacnet_devices": [
                {"device_id": 555, "address": "192.168.1.80", "vendor_name": "Trane"}
            ],
            "knx_devices": [],
            "ip_hosts": [],
        }
        saved_path = save_session("UnitTest_DiffBaseline", {}, base_state)
        filename = saved_path.name

        try:
            # 2. Configura lo stato live con un dispositivo modificato e uno nuovo
            state.clear()
            state.upsert_modbus(ModbusDevice(slave_id=10, protocol=Protocol.MODBUS_RTU, response_time_ms=25.0))
            state.upsert_bacnet(BACnetDevice(device_id=555, address="192.168.1.90", vendor_name="Trane")) # IP variato
            state.upsert_bacnet(BACnetDevice(device_id=777, address="192.168.1.95", vendor_name="Daikin")) # Nuovo

            async def _test():
                req = SessionDiffRequest(
                    baseline_filename=filename,
                    target_filename=None, # Live AppState
                )
                res = await routes.diff_sessions(req)
                self.assertIn("summary", res)
                self.assertIn("items", res)
                self.assertEqual(res["summary"]["total"]["added"], 1)     # BACnet 777
                self.assertEqual(res["summary"]["total"]["modified"], 1)  # BACnet 555
                self.assertEqual(res["summary"]["total"]["unchanged"], 1) # Modbus 10

            asyncio.run(_test())
        finally:
            delete_session(filename)


class TestBACnetBBMD(unittest.TestCase):
    """Test suite per gestione avanzata router BBMD e Foreign Device."""

    def test_bbmd_payload_decoders(self):
        from scanners.bacnet import decode_bdt_payload, decode_fdt_payload
        import socket, struct

        # BDT: 2 record x 10 byte
        rec1 = struct.pack("!4sH4s", socket.inet_aton("192.168.1.1"), 47808, socket.inet_aton("255.255.255.255"))
        rec2 = struct.pack("!4sH4s", socket.inet_aton("192.168.20.254"), 47809, socket.inet_aton("255.255.255.0"))
        bdt = decode_bdt_payload(rec1 + rec2)
        self.assertEqual(len(bdt), 2)
        self.assertEqual(bdt[0]["ip"], "192.168.1.1")
        self.assertEqual(bdt[0]["port"], 47808)
        self.assertEqual(bdt[0]["broadcast_mask"], "255.255.255.255")
        self.assertEqual(bdt[1]["ip"], "192.168.20.254")
        self.assertEqual(bdt[1]["port"], 47809)
        self.assertEqual(bdt[1]["broadcast_mask"], "255.255.255.0")

        # FDT: 2 record x 10 byte
        frec1 = struct.pack("!4sHHH", socket.inet_aton("10.0.1.50"), 47808, 60, 42)
        frec2 = struct.pack("!4sHHH", socket.inet_aton("10.0.2.77"), 47808, 120, 95)
        fdt = decode_fdt_payload(frec1 + frec2)
        self.assertEqual(len(fdt), 2)
        self.assertEqual(fdt[0]["ip"], "10.0.1.50")
        self.assertEqual(fdt[0]["ttl"], 60)
        self.assertEqual(fdt[0]["remaining_time"], 42)
        self.assertEqual(fdt[1]["ip"], "10.0.2.77")
        self.assertEqual(fdt[1]["remaining_time"], 95)

    def test_bbmd_tables_query_mock(self):
        import asyncio, socket, struct
        from scanners.bacnet import get_bbmd_tables

        class MockBBMDServer(asyncio.DatagramProtocol):
            def __init__(self):
                self.transport = None
            def connection_made(self, transport):
                self.transport = transport
            def datagram_received(self, data, addr):
                if len(data) >= 4 and data[0] == 0x81:
                    fn = data[1]
                    if fn == 0x02:  # Read-BDT
                        ip_b = socket.inet_aton("192.168.50.1")
                        mask_b = socket.inet_aton("255.255.255.255")
                        resp = bytes([0x81, 0x03, 0x00, 0x0E]) + struct.pack("!4sH4s", ip_b, 47808, mask_b)
                        self.transport.sendto(resp, addr)
                    elif fn == 0x06:  # Read-FDT
                        ip_b = socket.inet_aton("10.0.0.88")
                        resp = bytes([0x81, 0x07, 0x00, 0x0E]) + struct.pack("!4sHHH", ip_b, 47808, 60, 30)
                        self.transport.sendto(resp, addr)

        async def _run():
            loop = asyncio.get_running_loop()
            srv_tr, _ = await loop.create_datagram_endpoint(
                lambda: MockBBMDServer(),
                local_addr=("127.0.0.1", 47895)
            )
            try:
                res = await get_bbmd_tables("127.0.0.1", 47895, timeout=1.0)
                self.assertEqual(res["bbmd_ip"], "127.0.0.1")
                self.assertEqual(res["bbmd_port"], 47895)
                self.assertEqual(len(res["bdt"]), 1)
                self.assertEqual(res["bdt"][0]["ip"], "192.168.50.1")
                self.assertEqual(len(res["fdt"]), 1)
                self.assertEqual(res["fdt"][0]["ip"], "10.0.0.88")
            finally:
                srv_tr.close()
                await asyncio.sleep(0.02)

        asyncio.run(_run())

    def test_bbmd_routed_topology(self):
        state.clear()
        # 1 device locale
        state.upsert_bacnet(BACnetDevice(device_id=10, address="192.168.1.10", vendor_name="LocalBACnet"))
        # 1 device routed via BBMD
        state.upsert_bacnet(BACnetDevice(
            device_id=20,
            address="10.50.0.25",
            vendor_name="RemoteBACnet",
            bbmd_routed=True,
            routed_via="10.50.0.1:47808",
            tags=["bbmd_routed"]
        ))

        topo = state.get_topology()
        nodes = {n["id"]: n for n in topo["nodes"]}
        links = [(l["source"], l["target"]) for l in topo["links"]]

        # Verifica presenza del router BBMD
        router_id = "node:router:bbmd:10_50_0_1_47808"
        self.assertIn(router_id, nodes)
        self.assertEqual(nodes[router_id]["category"], "router")
        self.assertEqual(nodes[router_id]["parent_id"], "node:bus:bacnet_ip")

        # Verifica gerarchia del dispositivo routed
        dev20_id = "node:dev:bacnet:ip:20"
        self.assertIn(dev20_id, nodes)
        self.assertEqual(nodes[dev20_id]["parent_id"], router_id)
        self.assertTrue(nodes[dev20_id]["metrics"]["bbmd_routed"])
        self.assertIn((router_id, dev20_id), links)

        # Verifica dispositivo locale
        dev10_id = "node:dev:bacnet:ip:10"
        self.assertEqual(nodes[dev10_id]["parent_id"], "node:bus:bacnet_ip")
        self.assertIn(("node:bus:bacnet_ip", dev10_id), links)

    def test_bacnet_ip_scan_request_bbmd_fields(self):
        req = routes.BACnetIPScanRequest(
            iface="eth0",
            port="BAC0",
            bbmd_ip="192.168.10.1",
            bbmd_port=47808,
            bbmd_ttl=120,
        )
        self.assertEqual(req.bbmd_ip, "192.168.10.1")
        self.assertEqual(req.bbmd_port, 47808)
        self.assertEqual(req.bbmd_ttl, 120)


if __name__ == "__main__":
    unittest.main()


