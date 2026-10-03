# BHAM – REST & WebSocket API Reference
**Version:** 0.8.0  
**Base URL:** `http://<host>:8765/api/v1`  
**WebSocket URL:** `ws://<host>:8765/api/v1/ws`  
**Interactive Documentation:** [Swagger UI](http://localhost:8765/docs) | [ReDoc](http://localhost:8765/redoc)

---

## 📋 Table of Contents
1. [Architecture & Network Security](#1-architecture--network-security)
2. [Data Formats & HTTP Status Codes](#2-data-formats--http-status-codes)
3. [System & State Endpoints](#3-system--state-endpoints)
4. [Hardware & Session Setup](#4-hardware--session-setup)
5. [Scan & Sniffing Engines](#5-scan--sniffing-engines)
6. [Discovered Devices](#6-discovered-devices)
7. [Diagnostics & RS485 Bus Health](#7-diagnostics--rs485-bus-health)
8. [Modbus Smart Register Scan](#8-modbus-smart-register-scan)
9. [BACnet Object Explorer & BBMD Routing](#9-bacnet-object-explorer--bbmd-routing)
10. [Saved Sessions & Session Diff ("Before vs After")](#10-saved-sessions--session-diff-before-vs-after)
11. [BACS Help Register Maps](#11-bacs-help-register-maps)
12. [Reporting & As-Built Exports](#12-reporting--as-built-exports)
13. [WebSocket Live Telemetry Protocol](#13-websocket-live-telemetry-protocol)
14. [Code Integration Examples (cURL & Python)](#14-code-integration-examples-curl--python)
15. [Field Operational Tools ("Banco Prova & Override")](#15-field-operational-tools-banco-prova--override)
16. [Virtual Plant Simulator ("Demo / Offline Mode")](#16-virtual-plant-simulator-demo--offline-mode)
17. [Safe Mode Interlock ("Safety Write Barrier")](#17-safe-mode-interlock-safety-write-barrier)
18. [Crash-Proof Audit Journal (WAL & SHA-256)](#18-crash-proof-audit-journal-wal--sha-256)
19. [Modbus Profiles Library & Custom Manager](#19-modbus-profiles-library--custom-manager)

---

## 1. Architecture & Network Security

BHAM exposes a high-performance, asynchronous REST and WebSocket API built on **FastAPI** and **Starlette**. It runs on Python 3.12 with non-blocking I/O routines for Modbus RTU/TCP, BACnet/IP, KNXnet/IP, and promiscuous L2 packet sniffing.

### Network Binding & Multi-Device Access
- By default, BHAM binds to `0.0.0.0:8765`, enabling field engineers to run BHAM on a portable industrial PC or Raspberry Pi inside an electrical cabinet while accessing the UI or API from laptops, tablets, or test jigs over Ethernet or Wi-Fi.
- Accessible at `http://localhost:8765` locally or `http://<LAN_IP>:8765` across the local subnet.

### ⚠️ Security Notice
> **IMPORTANT:** BHAM is an industrial field diagnostic tool. By design, the REST and WebSocket endpoints require **no authentication** to streamline emergency field triage.
> - **DO NOT expose port 8765 directly to the public Internet.**
> - Use dedicated technician VLANs, point-to-point Ethernet cables, or an encrypted VPN (WireGuard / OpenVPN) when interacting across multi-tenant networks.
> - For persistent remote deployments, place BHAM behind a reverse proxy (e.g., Caddy or Nginx) enforcing TLS and HTTP Basic / OAuth2 authentication.

---

## 2. Data Formats & HTTP Status Codes

All REST endpoints consume and produce `application/json; charset=utf-8` unless delivering binary reports (Excel `.xlsx` or PDF `.pdf`).

### Standard Response Codes
| Status Code | Meaning | Description |
|---|---|---|
| `200 OK` | Success | The request was processed successfully. |
| `400 Bad Request` | Validation Error | Payload schema invalid or missing required parameters. |
| `404 Not Found` | Resource Missing | Specified session, file, or device instance does not exist. |
| `500 Internal Error` | Server Exception | An unhandled exception occurred during scan or hardware I/O. |

---

## 3. System & State Endpoints

### `GET /api/v1/health`
Returns the operational health of the BHAM daemon, software version, and count of currently active WebSocket clients.

**Response `200 OK` (`HealthResponse`):**
```json
{
  "status": "ok",
  "active_ws": 1,
  "version": "0.8.0"
}
```

---

### `GET /api/v1/state`
Returns the comprehensive live memory state: configuration, scan statuses, and all discovered devices across Modbus, BACnet, KNX, and ARP.

**Response `200 OK`:**
```json
{
  "session_config": {
    "site_name": "Hospital Wing B - HVAC Commissioning",
    "serial_port": "/dev/ttyUSB0",
    "serial_baudrate": 9600,
    "serial_parity": "N",
    "serial_stopbits": 1,
    "scan_iface": "eth0",
    "scan_ip": "192.168.1.150",
    "single_iface_mode": true
  },
  "modbus_devices": {},
  "bacnet_devices": {},
  "knx_devices": {},
  "ip_hosts": {}
}
```

---

### `DELETE /api/v1/state`
Clears in-memory discovered devices and resets the active commissioning state without terminating active background scans.

**Response `200 OK` (`StateClearResponse`):**
```json
{
  "cleared": true
}
```

---

### `GET /api/v1/topology`
Generates a structured, hierarchical plant topology graph suitable for SVG graph renderers, Network Graphs, or BIM integration.

**Hierarchy Structure:**
- **Level 0 (Root):** BHAM Host & Active Session
- **Level 1 (Channels):** Serial RS485 Bus (`port`, `baudrate`, `parity`), Ethernet Network Interface (`iface`, `ip`)
- **Level 2 (Routers):** BBMD BACnet IP Routers, KNXnet/IP Gateways
- **Level 3 (Devices):** Modbus Slaves, BACnet Controllers, KNX Nodes, ARP IP Hosts with telemetry badges

---

### `GET /api/v1/sessions`
Returns a list of all historical scan sessions tracked in the current daemon runtime.

---

### `GET /api/v1/sessions/{session_id}`
Returns granular telemetry and discovered items for a specific `session_id`.

---

## 4. Hardware & Session Setup

### `GET /api/v1/setup/serial-ports`
Enumerates all serial communication ports detected by the host OS. Highlights adapters commonly used for RS485 (FTDI FT232R, Silicon Labs CP210x, WCH CH340, Prolific PL2303).

**Response `200 OK` (`list[SerialPortInfo]`):**
```json
[
  {
    "port": "/dev/ttyUSB0",
    "description": "FT232R USB UART - FTDI",
    "hwid": "USB VID:PID=0403:6001 SER=A50285BI",
    "vid": 1027,
    "pid": 24577,
    "rs485_likely": true,
    "os_type": "linux"
  }
]
```

---

### `GET /api/v1/setup/network-interfaces`
Lists all active IPv4 network interface cards (NICs), physical link states, speeds, and host LAN IP addresses.

**Response `200 OK` (`NetworkInterfacesResponse`):**
```json
{
  "interfaces": [
    {
      "name": "eth0",
      "ip": "192.168.1.50",
      "netmask": "255.255.255.0",
      "is_up": true,
      "speed_mbps": 1000,
      "is_wireless": false
    }
  ],
  "single_iface_mode": true,
  "lan_ips": ["192.168.1.50"],
  "port": 8765
}
```

---

### `GET /api/v1/hardware/self-test`
Executes an automated, non-destructive hardware and OS permission self-test.
- **Serial test:** Tests opening and closing the configured port, measuring latency in milliseconds.
- **Network test:** Verifies active default route, socket binding, and local broadcast capability.
- **Privileges test:** Verifies `dialout` group membership (Linux) or Administrator privileges (Windows), plus packet capture capabilities (`cap_net_raw` / Npcap).

**Response `200 OK` (`HardwareSelfTestResponse`):**
```json
{
  "timestamp": 1759489200.0,
  "overall": "ok",
  "serial": {
    "status": "ok",
    "port": "/dev/ttyUSB0",
    "open_latency_ms": 3.4
  },
  "network": {
    "status": "ok",
    "active_interfaces": 1
  },
  "privileges": {
    "status": "ok",
    "dialout": true,
    "cap_net_raw": true
  }
}
```

---

### `POST /api/v1/setup/configure`
Applies physical hardware settings (serial port, baudrate, network interfaces, and site description) for the current session.

**Request Body (`ConfigureRequest`):**
```json
{
  "serial_port": "/dev/ttyUSB0",
  "serial_baudrate": 9600,
  "serial_parity": "N",
  "serial_stopbits": 1,
  "scan_iface": "eth0",
  "client_iface": "eth0",
  "single_iface_mode": true,
  "site_name": "Hospital Wing B"
}
```

**Response `200 OK` (`ConfigureResponse`):**
```json
{
  "configured": true,
  "config": {
    "site_name": "Hospital Wing B",
    "serial_port": "/dev/ttyUSB0",
    "serial_baudrate": 9600,
    "serial_parity": "N",
    "serial_stopbits": 1,
    "scan_iface": "eth0",
    "client_iface": "eth0",
    "single_iface_mode": true
  }
}
```

---

### `GET /api/v1/setup/config`
Retrieves the currently active configuration (`ConfigActiveResponse`).

---

## 5. Scan & Sniffing Engines

All scan tasks execute asynchronously in background worker threads or asyncio event loops. They return immediately with a `session_id`. Telemetry and real-time progress are broadcasted over the WebSocket channel.

### `POST /api/v1/scan/modbus/rtu`
Initiates active Modbus RTU sweep across RS485. Utilizes a 3-phase algorithm:
1. **Phase 0:** Silent baudrate detection.
2. **Phase 1:** Sentinel ID Early Exit ({1, 2, 10}).
3. **Phase 2:** Fast full ID sweep.

**Request Body (`ModbusRTUScanRequest`):**
```json
{
  "port": "/dev/ttyUSB0",
  "baudrates": [9600, 19200, 38400, 115200],
  "parities": ["N", "E"],
  "stopbits": [1],
  "id_range": [1, 2, 3, 4, 5, 10, 20],
  "spy_ids": [1, 2, 10]
}
```

**Response `200 OK` (`ScanActionResponse`):**
```json
{
  "session_id": "rtu_20261003_120000",
  "status": "started"
}
```

---

### `POST /api/v1/scan/modbus/tcp`
Initiates Modbus TCP polling against individual IPs or CIDR blocks across single or multiple ports (e.g. `502`, `503`, `5020`).

**Request Body (`ModbusTCPScanRequest`):**
```json
{
  "hosts": ["192.168.1.10", "192.168.1.11", "192.168.1.0/28"],
  "tcp_port": "502, 503",
  "unit_ids": [1, 2]
}
```

**Response `200 OK` (`ScanActionResponse`):**
```json
{
  "session_id": "tcp_20261003_120100",
  "status": "started"
}
```

---

### `POST /api/v1/scan/serial/sniff`
Starts **Zero-TX Stealth Mode** passive sniffing on RS485. Listens to Modbus RTU and BACnet MS-TP traffic without transmitting a single electrical pulse. Calculates Bus Health metrics (PER, Bus Load, FPS) in real time.

**Request Body (`SerialSniffRequest`):**
```json
{
  "port": "/dev/ttyUSB0",
  "baudrate": 0,
  "parity": "auto",
  "stopbits": 1,
  "protocol_filter": "auto",
  "duration": 30.0
}
```

**Response `200 OK` (`ScanActionResponse`):**
```json
{
  "session_id": "sniff_20261003_120200",
  "status": "started"
}
```

---

### `POST /api/v1/scan/bacnet/ip`
Transmits BACnet Who-Is broadcast telegrams (`0xBAC0` through `0xBACF`), interrogates discovered devices for Object List and vendor metadata, and supports Foreign Device traversal through BBMD routers.

**Request Body (`BACnetIPScanRequest`):**
```json
{
  "iface": "eth0",
  "port": "BAC0..BAC2",
  "bbmd_ip": "192.168.10.1",
  "bbmd_port": 47808,
  "bbmd_ttl": 60
}
```

**Response `200 OK` (`ScanActionResponse`):**
```json
{
  "session_id": "bacnet_20261003_120300",
  "status": "started"
}
```

---

### `POST /api/v1/scan/knx/ip`
Sends KNXnet/IP `SEARCH_REQUEST` telegrams via UDP multicast (`224.0.23.12:3671`) and broadcast fallback (`255.255.255.255:3671`). Decodes DIB descriptors, individual addresses (`Area.Line.Device`), friendly names, and serial numbers.

**Request Body (`KNXIPScanRequest`):**
```json
{
  "iface": "eth0",
  "port": 3671,
  "timeout": 3.5
}
```

**Response `200 OK` (`ScanActionResponse`):**
```json
{
  "session_id": "knx_20261003_120400",
  "status": "started"
}
```

---

### `POST /api/v1/scan/arp`
Launches promiscuous Layer-2 ARP capture using Scapy. Discovers unadvertised IP hosts on the local Ethernet segment and resolves MAC OUI vendor signatures.

**Request Body (`ARPSniffRequest`):**
```json
{
  "iface": "eth0",
  "duration": 30.0
}
```

**Response `200 OK` (`ScanActionResponse`):**
```json
{
  "session_id": "arp_20261003_120500",
  "status": "started"
}
```

---

### `POST /api/v1/scan/abort`
Immediately terminates all active scans and passive sniffers, freeing serial ports and raw sockets.

**Response `200 OK` (`ScanAbortResponse`):**
```json
{
  "aborted": true,
  "sessions": ["rtu_20261003_120000", "arp_20261003_120500"]
}
```

---

### `POST /api/v1/scan/abort/{session_id}`
Aborts a specific scan task by its identifier.

**Response `200 OK` (`ScanAbortSingleResponse`):**
```json
{
  "aborted": true
}
```

---

## 6. Discovered Devices

Retrieve filtered lists of discovered hardware in active memory:

| Endpoint | Protocol | Output Model | Key Fields Returned |
|---|---|---|---|
| `GET /api/v1/devices/modbus` | Modbus RTU/TCP | `list[ModbusDevice]` | `slave_id`, `protocol`, `serial_params`, `ip`, `tcp_port`, `vendor_name`, `product_code`, `registers` |
| `GET /api/v1/devices/bacnet` | BACnet/IP | `list[BACnetDevice]` | `device_id`, `address`, `vendor_name`, `model_name`, `firmware_revision`, `object_count`, `object_list` |
| `GET /api/v1/devices/knx` | KNXnet/IP | `list[KNXDevice]` | `individual_address`, `device_name`, `serial_number`, `mac_address`, `ip_address`, `medium` |
| `GET /api/v1/devices/hosts` | L2 ARP Hosts | `list[IPHost]` | `ip`, `mac`, `vendor_oui`, `hostname`, `first_seen`, `last_seen` |

---

## 7. Diagnostics & RS485 Bus Health

### `POST /api/v1/diag/modbus/fc43`
Queries a specific Modbus RTU slave using Function Code 43 / MEI Type 0x0E (Read Device Identification).

**Request Body (`FC43Request`):**
```json
{
  "port": "/dev/ttyUSB0",
  "baudrate": 9600,
  "parity": "N",
  "stopbits": 1,
  "slave_id": 1
}
```

**Response `200 OK` (`FC43Response`):**
```json
{
  "slave_id": 1,
  "supported": true,
  "vendor_name": "Schneider Electric",
  "product_code": "PM5350",
  "revision": "v2.1.0",
  "vendor_url": "https://www.se.com",
  "product_name": "PowerLogic Power Meter",
  "model_name": "PM5350",
  "user_application_name": "Incomer 1",
  "error": null
}
```

---

### `GET /api/v1/diag/serial/health`
Returns real-time physical layer metrics captured by the Zero-TX sniffer on RS485 (`BusHealth`):
- **PER % (Packet Error Rate):** Percentage of corrupted or CRC-failed packets (<1% = pristine; >5% = critical cable or termination faults).
- **Bus Load %:** Estimated transmission time occupancy on the wire.
- **FPS:** Telegram frame rate per second.
- **Heuristic Warnings:** Automatic detection of missing 120Ω termination, polarity inversions, or baudrate mismatches.

**Response `200 OK` (`Optional[BusHealth]`):**
```json
{
  "total_frames": 1240,
  "crc_errors": 3,
  "per_percent": 0.24,
  "bus_load_percent": 14.8,
  "fps": 32.5,
  "active_nodes": 7,
  "heuristic_warnings": []
}
```

---

## 8. Modbus Smart Register Scan

### `POST /api/v1/modbus/smart-scan`
*(Alias: `POST /api/v1/scan/modbus/smart-scan`)*  
Performs predictive block probing across standard register boundaries for Holding Registers (FC03) and Input Registers (FC04). Automatically decodes:
- Raw Unsigned 16-bit Integer (`raw_dec`, `raw_hex`)
- Signed 16-bit Integer (`int16`)
- IEEE 754 32-bit Floating Point (`float32`)

**Request Body (`ModbusSmartScanBody`):**
```json
{
  "slave_id": 1,
  "protocol": "rtu",
  "port": "/dev/ttyUSB0",
  "baudrate": 9600,
  "parity": "N",
  "stopbits": 1
}
```

**Response `200 OK` (`ModbusSmartScanResponse`):**
```json
{
  "slave_id": 1,
  "endpoint": "/dev/ttyUSB0",
  "elapsed_ms": 142.5,
  "found_count": 4,
  "registers": [
    {
      "address": 100,
      "type": "holding",
      "raw_dec": 235,
      "raw_hex": "0x00EB",
      "int16": 235,
      "float32": null
    }
  ],
  "error": null
}
```

---

## 9. BACnet Object Explorer & BBMD Routing

### `GET /api/v1/bacnet/devices/{device_id}/objects`
### `POST /api/v1/bacnet/devices/{device_id}/objects`
Reads the complete `object-list` of a BACnet controller and probes runtime properties: `presentValue`, `objectName`, `units`, and flags.

**Query / Body Params:**
- `address`: Optional explicit IP:Port string (e.g. `192.168.1.100:47808`).

**Response `200 OK` (`BACnetObjectExplorerResponse`):**
```json
{
  "device_id": 1234,
  "address": "192.168.1.100:47808",
  "count": 2,
  "objects": [
    {
      "identifier": "analogInput:1",
      "type": "analogInput",
      "instance": 1,
      "name": "Supply_Air_Temp",
      "present_value": "21.4",
      "units": "°C"
    },
    {
      "identifier": "binaryValue:2",
      "type": "binaryValue",
      "instance": 2,
      "name": "Fan_Run_Status",
      "present_value": "active",
      "units": ""
    }
  ],
  "error": null
}
```

---

### BBMD Router Endpoints
- `GET /api/v1/bacnet/bbmd/tables?bbmd_ip=192.168.10.1&bbmd_port=47808`: Retrieves both BDT and FDT tables simultaneously (`BBMDInfoResponse`).
- `GET /api/v1/bacnet/bbmd/bdt?bbmd_ip=192.168.10.1`: Reads the Broadcast Distribution Table (`list[BBDTEntry]`).
- `GET /api/v1/bacnet/bbmd/fdt?bbmd_ip=192.168.10.1`: Reads the Foreign Device Table (`list[FDTEntry]`).

---

## 10. Saved Sessions & Session Diff ("Before vs After")

### Session Management Endpoints
- `POST /api/v1/saved-sessions/save`: Saves active memory to disk under `sessions/<timestamp>_<name>.json` (`SaveSessionResponse`).
  - Request: `{"name": "Site_A_Baseline"}`
- `GET /api/v1/saved-sessions/list`: Lists all saved JSON sessions with device tallies (`list[SavedSessionMeta]`).
- `GET /api/v1/saved-sessions/{filename}`: Retrieves full JSON payload of a stored session.
- `DELETE /api/v1/saved-sessions/{filename}`: Deletes a stored session file (`DeleteSessionResponse`).
- `POST /api/v1/saved-sessions/{filename}/restore`: Restores stored session into the live state (`RestoreSessionResponse`).

---

### `POST /api/v1/sessions/diff`
Performs analytical comparison between two sessions or between a stored baseline and the live runtime.

**Request Body (`SessionDiffRequest`):**
```json
{
  "baseline_file": "20261001_SiteA_Initial.json",
  "current_file": null
}
```
*(Leave `current_file: null` to compare against active live state).*

**Response `200 OK` (`SessionDiffResult`):**
```json
{
  "baseline_name": "SiteA_Initial",
  "current_name": "Live State",
  "summary": {
    "added": 2,
    "removed": 1,
    "modified": 3,
    "unchanged": 12
  },
  "changes": [
    {
      "entity_type": "modbus",
      "identifier": "Modbus ID #12",
      "change_type": "modified",
      "details": "Baudrate changed from 9600 to 19200; Response time: 24ms -> 12ms",
      "old_data": { "baudrate": 9600 },
      "new_data": { "baudrate": 19200 }
    }
  ]
}
```

---

## 11. BACS Help Register Maps

Correlates discovered Modbus registers with engineering tag descriptions, engineering units, and scaling factors:
- `POST /api/v1/maps/import`: Bulk imports JSON mapping definitions (`MapsImportResponse`).
- `GET /api/v1/maps/export`: Exports all loaded mapping points as a consolidated JSON.
- `GET /api/v1/maps/{slave_id}`: Retrieves all defined points for a specific Modbus slave (`SlaveMapResponse`).

---

## 12. Reporting & As-Built Exports

### `GET /api/v1/report/excel`
Generates and downloads a multi-tab workbook (`.xlsx`) generated via **openpyxl**:
1. *Panoramica Impianto* (Metadata, configuration, device counts)
2. *Modbus Dispositivi* (Addresses, baudrates, latency, vendor info)
3. *BACnet Dispositivi* (Device instance IDs, IP:port, model, firmware)
4. *KNX Dispositivi* (Individual addresses, friendly names, serials)
5. *Host IP Rete* (IP, MAC, Vendor OUI)
6. *BACnet Oggetti* (Deep object-list breakdown)
7. *Mappa Registri Modbus* (Smart scan registers and BACS Help points)
8. *Diagnostica Bus RS485* (Bus Health PER %, load, errors)

---

### `GET /api/v1/report/pdf`
Generates and downloads an engineering report (`.pdf`) using **ReportLab**:
- Clean cover page with plant identification and timestamps.
- Summary KPI cards.
- Structured tables for each protocol.
- RS485 Bus Health diagnostic graphs.
- Dynamic page numbering ("Page X of Y") via two-pass canvas layout.

---

## 13. WebSocket Live Telemetry Protocol

**Endpoint:** `ws://<host>:8765/api/v1/ws`

The WebSocket channel delivers asynchronous event notifications to connected frontend clients and external monitoring tools.

### Client Commands
To keep the socket alive, send standard ping frames or JSON pings:
```json
{ "type": "ping" }
```

### Server Broadcast Events
#### 1. Scan Progress (`scan_progress`)
```json
{
  "type": "scan_progress",
  "data": {
    "session_id": "rtu_20261003_120000",
    "protocol": "modbus_rtu",
    "percent": 45.0,
    "current_target": "Slave ID 112",
    "found_so_far": 8
  }
}
```

#### 2. Device Discovered (`device_found`)
```json
{
  "type": "device_found",
  "data": {
    "protocol": "bacnet_ip",
    "device": {
      "device_id": 2001,
      "address": "192.168.1.120:47808",
      "vendor_name": "Carrier Corporation",
      "model_name": "30XA Chiller"
    }
  }
}
```

#### 3. Bus Health Update (`bus_health_update`)
```json
{
  "type": "bus_health_update",
  "data": {
    "per_percent": 0.4,
    "bus_load_percent": 18.2,
    "fps": 24.1,
    "active_nodes": 6,
    "crc_errors": 2,
    "total_frames": 500
  }
}
```

#### 4. Asynchronous Log Record (`log_record`)
```json
{
  "type": "log_record",
  "data": {
    "timestamp": "2026-10-03T12:05:01Z",
    "level": "INFO",
    "message": "BACnet/IP Who-Is response received from 192.168.1.120 (Device 2001)"
  }
}
```

---

## 14. Code Integration Examples (cURL & Python)

### cURL Integration Examples

#### 1. Hardware Self-Test
```bash
curl -X GET "http://localhost:8765/api/v1/hardware/self-test" -H "Accept: application/json"
```

#### 2. Trigger Modbus RTU Scan
```bash
curl -X POST "http://localhost:8765/api/v1/scan/modbus/rtu" \
  -H "Content-Type: application/json" \
  -d '{
    "port": "/dev/ttyUSB0",
    "baudrates": [9600, 19200],
    "parities": ["N", "E"],
    "stopbits": [1],
    "id_range": [1, 2, 3, 4, 5, 10, 20]
  }'
```

#### 3. Download As-Built Excel Report
```bash
curl -X GET "http://localhost:8765/api/v1/report/excel" -o "as_built_report.xlsx"
```

---

### Python Automated Commissioning Script

```python
#!/usr/bin/env python3
import time
import requests
import json

BASE_URL = "http://localhost:8765/api/v1"

def main():
    # 1. Check daemon health
    res = requests.get(f"{BASE_URL}/health")
    health = res.json()
    print(f"[+] BHAM Daemon online: v{health['version']} (active WS: {health['active_ws']})")

    # 2. Hardware Self-Test
    test_res = requests.get(f"{BASE_URL}/hardware/self-test").json()
    print(f"[+] Hardware Self-Test status: {test_res['overall']}")

    # 3. Configure site session
    cfg = {
        "serial_port": "/dev/ttyUSB0",
        "serial_baudrate": 9600,
        "serial_parity": "N",
        "scan_iface": "eth0",
        "site_name": "DataCenter Cooling Commissioning"
    }
    requests.post(f"{BASE_URL}/setup/configure", json=cfg)
    print("[+] Session configured successfully.")

    # 4. Trigger BACnet Who-Is Broadcast
    scan = requests.post(f"{BASE_URL}/scan/bacnet/ip", json={"iface": "eth0", "port": "BAC0"}).json()
    print(f"[+] BACnet scan started: {scan['session_id']}")

    # Polling wait for scan to complete
    time.sleep(4)

    # 5. Fetch Discovered Devices
    devices = requests.get(f"{BASE_URL}/devices/bacnet").json()
    print(f"[+] BACnet Devices Found: {len(devices)}")
    for d in devices:
        print(f"    - Device #{d['device_id']}: {d.get('vendor_name')} ({d.get('model_name')}) at {d.get('address')}")

    # 6. Download PDF Report
    pdf = requests.get(f"{BASE_URL}/report/pdf")
    with open("Commissioning_Report.pdf", "wb") as f:
        f.write(pdf.content)
    print("[+] Exported Commissioning_Report.pdf successfully!")

if __name__ == "__main__":
    main()
```

---

## 15. Field Operational Tools ("Banco Prova & Override")

BHAM v0.8.0 introduces an integrated field test bench to read and override registers and objects on live Modbus and BACnet field networks without requiring external bulky tools.

### Modbus Quick Read
- **Endpoint:** `POST /api/v1/tools/modbus/read`
- **Description:** Performs synchronous reading of Modbus registers or coils via RTU (serial) or TCP (Ethernet). Decodes raw registers into multiple representations: UInt16, Int16 signed, IEEE-754 Float32 (Big-Endian and Word-Swapped Little-Endian), and Hex.
- **Request Body (`ModbusQuickReadRequest`):**
  ```json
  {
    "protocol": "rtu",
    "port": "/dev/ttyUSB0",
    "baudrate": 9600,
    "parity": "N",
    "slave_id": 1,
    "function_code": 3,
    "address": 0,
    "count": 2,
    "timeout": 2.0
  }
  ```
- **Response (`ModbusQuickReadResponse`):**
  ```json
  {
    "status": "ok",
    "elapsed_ms": 14.2,
    "registers": [17280, 0],
    "hex_values": ["0x4380", "0x0000"],
    "int16_values": [17280, 0],
    "float32_be": [256.0],
    "float32_le": [0.0],
    "coils": []
  }
  ```

### Modbus Quick Write
- **Endpoint:** `POST /api/v1/tools/modbus/write`
- **Description:** Forces single or multiple Modbus coils and registers (FC05, FC06, FC15, FC16). Automatically encodes floats (IEEE-754 standard and word-swapped) and signed 16-bit integers into register payloads.
- **Request Body (`ModbusQuickWriteRequest`):**
  ```json
  {
    "protocol": "rtu",
    "port": "/dev/ttyUSB0",
    "slave_id": 1,
    "function_code": 16,
    "address": 0,
    "values": [21.5],
    "data_type": "float32"
  }
  ```
- **Response (`ModbusQuickWriteResponse`):**
  ```json
  {
    "status": "ok",
    "elapsed_ms": 18.7,
    "written_values": [21.5],
    "registers_written": 2
  }
  ```

### BACnet Point Commander: Write / Override
- **Endpoint:** `POST /api/v1/tools/bacnet/write`
- **Description:** Overrides `presentValue` on standard BACnet objects (`analogOutput`, `binaryOutput`, `multiStateOutput`, `analogValue`, etc.) with full Priority Array control (defaulting to Priority 8: Manual Operator).
- **Request Body (`BACnetPointOverrideRequest`):**
  ```json
  {
    "device_id": 1001,
    "object_type": "analogOutput",
    "instance": 1,
    "value": 45.0,
    "priority": 8
  }
  ```
- **Response (`BACnetPointOverrideResponse`):**
  ```json
  {
    "status": "ok",
    "elapsed_ms": 22.1,
    "device_id": 1001,
    "object_type": "analogOutput",
    "instance": 1,
    "priority": 8,
    "written_value": 45.0,
    "relinquished": false
  }
  ```

### BACnet Point Commander: Relinquish
- **Endpoint:** `POST /api/v1/tools/bacnet/relinquish`
- **Description:** Relinquishes manual override by writing `NULL` to the Priority Array slot at the designated priority level, allowing the automatic control logic (e.g. PID loop at Priority 9 or Baseline at Priority 16) to regain control.
- **Request Body (`BACnetRelinquishRequest`):**
  ```json
  {
    "device_id": 1001,
    "object_type": "analogOutput",
    "instance": 1,
    "priority": 8
  }
  ```
- **Response (`BACnetPointOverrideResponse`):**
  ```json
  {
    "status": "ok",
    "elapsed_ms": 19.4,
    "device_id": 1001,
    "object_type": "analogOutput",
    "instance": 1,
    "priority": 8,
    "written_value": null,
    "relinquished": true
  }
  ```

---

## 16. Virtual Plant Simulator ("Demo / Offline Mode")

BHAM v0.8.0 includes an emulated HVAC/BACS virtual plant engine that allows full offline testing, training, and client demos without physical RS485 or BACnet hardware.

### Get Simulator Status
- **Endpoint:** `GET /api/v1/demo/status`
- **Response (`DemoStatusResponse`):**
  ```json
  {
    "active": true,
    "summary": {
      "modbus_slaves": 3,
      "bacnet_devices": 2,
      "knx_devices": 2,
      "arp_hosts": 3
    }
  }
  ```

### Toggle Simulator Mode
- **Endpoint:** `POST /api/v1/demo/toggle`
- **Description:** Inverts active simulation state. When enabled, populates simulated devices (Chiller Modbus Slave 1, Pump Modbus Slave 2, Power Meter Modbus Slave 3, UTA BACnet Device 1001, VAV Device 1002, KNX 1.1.1 / 1.1.2) and starts dynamic telemetry oscillation. When disabled, restores clean live telemetry.
- **Response (`DemoToggleResponse`):**
  ```json
  {
    "active": true,
    "message": "Modalità Demo Attivata: caricati dispositivi virtuali Modbus, BACnet, KNX e ARP con telemetria sintetica."
  }
  ```

### Enable / Disable Simulator
- **Endpoints:** `POST /api/v1/demo/enable` and `POST /api/v1/demo/disable`

---

## 17. Safe Mode Interlock ("Safety Write Barrier")

The Safe Mode Interlock prevents accidental writes and overrides on active facility equipment (chillers, pumps, valves, and energy meters). All write operations across Modbus RTU/TCP and BACnet are blocked with HTTP `403 Forbidden` unless the system is explicitly armed with technician credentials and a bounded authorization window.

### Get Safe Mode Status
- **Endpoint:** `GET /api/v1/safe-mode/status`
- **Response (`SafeModeStatusResponse`):**
  ```json
  {
    "armed": true,
    "operator": "Giuliano (Lead Commissioning)",
    "job_order": "COMM-2026-OSPEDALE-01",
    "armed_at": "2026-10-03T20:45:00+02:00",
    "expires_at": "2026-10-03T21:15:00+02:00",
    "remaining_seconds": 1204
  }
  ```

### Arm Safe Mode (Unlock Write Operations)
- **Endpoint:** `POST /api/v1/safe-mode/arm`
- **Request Body (`SafeModeArmRequest`):**
  ```json
  {
    "operator": "Giuliano (Lead Commissioning)",
    "job_order": "COMM-2026-OSPEDALE-01",
    "duration_minutes": 30
  }
  ```
- **Response (`SafeModeStatusResponse`):** Returns updated status with `armed: true` and calculated `expires_at`.

### Disarm Safe Mode (Immediate Manual Lock)
- **Endpoint:** `POST /api/v1/safe-mode/disarm`
- **Description:** Instantly revokes write permissions and locks all field bus channels.
- **Response (`SafeModeStatusResponse`):** Returns updated status with `armed: false`.

---

## 18. Crash-Proof Audit Journal (WAL & SHA-256)

Every write maneuver (Modbus register write, BACnet priority override, and safe-mode state transition) is immutably logged to an append-only Write-Ahead Log (`audit_journal.jsonl`) with forced disk commit (`os.fsync`) prior to raw byte transmission, and linked via a cryptographic SHA-256 blockchain-style hash chain.

### Get Audit Journal Entries
- **Endpoint:** `GET /api/v1/audit/journal?limit=100`
- **Response:** Array of `AuditJournalEntry`:
  ```json
  [
    {
      "entry_id": "JNL-000001",
      "timestamp_iso": "2026-10-03T20:50:12.345678+02:00",
      "phase": "INTENT",
      "action": "modbus_write_single_register",
      "protocol": "modbus",
      "operator": "Giuliano",
      "job_order": "COMM-2026-OSPEDALE-01",
      "target": {
        "slave_id": 1,
        "function_code": 6,
        "address": 100,
        "value_requested": 450
      },
      "status": "RECORDED",
      "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
      "entry_hash": "a1b2c3d4e5f6..."
    }
  ]
  ```

### Verify Audit Journal Integrity
- **Endpoint:** `GET /api/v1/audit/verify`
- **Description:** Performs full forensic re-computation of the SHA-256 chain from the genesis record to the latest entry to detect manual tampering or bit corruption.
- **Response (`AuditIntegrityResponse`):**
  ```json
  {
    "total_entries": 42,
    "valid": true,
    "corrupted_index": null,
    "last_hash": "8f3b2c1e4d5a...",
    "error": null
  }
  ```

### Export Audit Journal
- **Endpoint:** `GET /api/v1/audit/export`
- **Description:** Returns the complete audit journal log formatted for download as an official verification artifact.

---

## 19. Modbus Profiles Library & Custom Manager

Provides built-in and user-customizable Modbus register structures with point names, data formats, units, and scaling multipliers for immediate application to scanned devices.

### List Profiles
- **Endpoint:** `GET /api/v1/profiles?category=all`
- **Query Parameters:** `category` (`all`, `multimeter`, `energy_heat`, `actuator_hvac`, `custom`).
- **Response:** Array of `ProfileSummary`:
  ```json
  [
    {
      "id": "abb_b23",
      "name": "ABB B23",
      "manufacturer": "ABB",
      "model": "B23 Steel/Bronze/Silver",
      "category": "multimeter",
      "is_builtin": true,
      "point_count": 8,
      "description": "Contatore di energia compatto trifase su barra DIN"
    }
  ]
  ```

### Get Profile Definition
- **Endpoint:** `GET /api/v1/profiles/{profile_id}`
- **Response:** Full `ProfileDefinition` including complete `points` array with registers, formats, scaling factors, units, and descriptions.

### Create / Update Custom Profile
- **Endpoint:** `POST /api/v1/profiles/custom`
- **Request Body (`CustomProfileCreateRequest`):** Full profile specification including `id`, `name`, `manufacturer`, `model`, `category`, and `points`.
- **Response:** Created/updated profile object.

### Delete Custom Profile
- **Endpoint:** `DELETE /api/v1/profiles/custom/{profile_id}`
- **Description:** Deletes a user-defined custom profile from storage. Built-in profiles cannot be deleted.

### Apply Profile to Slave ID
- **Endpoint:** `POST /api/v1/profiles/apply`
- **Description:** Binds a profile to an existing Modbus slave on the active bus, injecting all register points into the live device register view and MapsManager.
- **Request Body (`ApplyProfileRequest`):**
  ```json
  {
    "slave_id": 1,
    "profile_id": "schneider_iem3150"
  }
  ```
- **Response:**
  ```json
  {
    "status": "ok",
    "slave_id": 1,
    "profile_id": "schneider_iem3150",
    "applied_registers": 11,
    "message": "Applicato profilo 'Schneider Acti9 iEM3150' a slave #1 (11 registri mappati)"
  }
  ```


