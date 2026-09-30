"""
BHAM – Session Diff Engine (Intelligence & "Prima vs Dopo")
Confronto deterministico tra due istantanee d'impianto:
- Baseline (es. sessione di collaudo precedente o as-built)
- Target (es. sessione attuale, nuova scansione o stato live AppState)

Classifica ogni dispositivo in:
- ADDED (🟢 Nuovo apparato comparso)
- REMOVED (🔴 Apparato scomparso/offline)
- MODIFIED (🟡 Parametri o configurazione cambiati)
- UNCHANGED (Dispositivo stabile)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from data.models import (
    DeviceDiffItem,
    DiffStatus,
    FieldChange,
    ProtocolDiffSummary,
    SessionDiffResult,
    utc_now,
)

log = logging.getLogger("bham").getChild("session_diff")


def _to_dict(item: Any) -> dict[str, Any]:
    """Converte un oggetto (Pydantic model o dict) in dizionario standard."""
    if isinstance(item, dict):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    if hasattr(item, "__dict__"):
        return dict(item.__dict__)
    return {}


def _make_modbus_key(d: dict[str, Any]) -> str:
    """Genera la chiave logica d'impianto per dispositivi Modbus."""
    proto = str(d.get("protocol", "modbus_rtu")).lower()
    slave_id = d.get("slave_id")
    ip = d.get("ip")
    if "tcp" in proto or ip:
        tcp_port = d.get("tcp_port", 502)
        return f"modbus_tcp:{ip}:{tcp_port}:{slave_id}"
    return f"modbus_rtu:{slave_id}"


def _make_knx_key(d: dict[str, Any]) -> str:
    """Genera la chiave logica d'impianto per dispositivi KNX."""
    indiv_addr = d.get("individual_address")
    if indiv_addr:
        return f"knx:{indiv_addr}"
    mac = d.get("mac_address")
    if mac:
        return f"knx:mac:{mac.upper()}"
    return f"knx:{d.get('ip_address')}:{d.get('port', 3671)}"


def _compare_modbus(
    base_devs: list[dict[str, Any]],
    target_devs: list[dict[str, Any]],
) -> list[DeviceDiffItem]:
    items: list[DeviceDiffItem] = []
    base_map = {_make_modbus_key(d): d for d in base_devs}
    target_map = {_make_modbus_key(d): d for d in target_devs}

    all_keys = sorted(set(base_map.keys()) | set(target_map.keys()))

    for key in all_keys:
        in_base = key in base_map
        in_target = key in target_map
        b_dev = base_map.get(key)
        t_dev = target_map.get(key)

        slave_id = (t_dev or b_dev).get("slave_id", "?")
        proto = (t_dev or b_dev).get("protocol", "modbus_rtu")
        is_tcp = "tcp" in str(proto).lower() or bool((t_dev or b_dev).get("ip"))

        if is_tcp:
            ip = (t_dev or b_dev).get("ip", "")
            port = (t_dev or b_dev).get("tcp_port", 502)
            label = f"Modbus TCP – Slave #{slave_id} ({ip}:{port})"
            identifier = f"TCP Slave #{slave_id} [{ip}]"
        else:
            serial_port = (t_dev or b_dev).get("serial_params", {}).get("port") if (t_dev or b_dev).get("serial_params") else "RS485"
            label = f"Modbus RTU – Slave #{slave_id} ({serial_port})"
            identifier = f"RTU Slave #{slave_id}"

        if in_target and not in_base:
            items.append(DeviceDiffItem(
                protocol="modbus",
                identifier=identifier,
                label=label,
                status=DiffStatus.ADDED,
                target_data=t_dev,
            ))
        elif in_base and not in_target:
            items.append(DeviceDiffItem(
                protocol="modbus",
                identifier=identifier,
                label=label,
                status=DiffStatus.REMOVED,
                baseline_data=b_dev,
            ))
        else:
            changes: list[FieldChange] = []
            assert b_dev is not None and t_dev is not None

            # Controllo parametri di comunicazione
            if is_tcp:
                if b_dev.get("ip") != t_dev.get("ip"):
                    changes.append(FieldChange(
                        field="ip",
                        baseline=b_dev.get("ip"),
                        target=t_dev.get("ip"),
                        description="Indirizzo IP variato",
                    ))
                if b_dev.get("tcp_port") != t_dev.get("tcp_port"):
                    changes.append(FieldChange(
                        field="tcp_port",
                        baseline=b_dev.get("tcp_port"),
                        target=t_dev.get("tcp_port"),
                        description="Porta TCP variata",
                    ))
            else:
                b_sp = b_dev.get("serial_params") or {}
                t_sp = t_dev.get("serial_params") or {}
                for sp_prop, sp_desc in [
                    ("baudrate", "Baudrate RS485"),
                    ("parity", "Parità seriale"),
                    ("stopbits", "Bit di stop"),
                    ("port", "Porta seriale"),
                ]:
                    if b_sp.get(sp_prop) != t_sp.get(sp_prop) and (b_sp.get(sp_prop) or t_sp.get(sp_prop)):
                        changes.append(FieldChange(
                            field=f"serial_{sp_prop}",
                            baseline=b_sp.get(sp_prop),
                            target=t_sp.get(sp_prop),
                            description=f"{sp_desc} variata",
                        ))

            # Registri e tag
            b_regs = b_dev.get("registers") or {}
            t_regs = t_dev.get("registers") or {}
            if len(b_regs) != len(t_regs):
                changes.append(FieldChange(
                    field="registers_count",
                    baseline=len(b_regs),
                    target=len(t_regs),
                    description=f"Conteggio registri letti: {len(b_regs)} ➔ {len(t_regs)}",
                ))

            # Latenza risposta (se scostamento > 200ms)
            b_rt = b_dev.get("response_time_ms")
            t_rt = t_dev.get("response_time_ms")
            if b_rt is not None and t_rt is not None:
                if abs(float(t_rt) - float(b_rt)) > 200.0:
                    changes.append(FieldChange(
                        field="response_time_ms",
                        baseline=round(float(b_rt), 1),
                        target=round(float(t_rt), 1),
                        description=f"Variazione latenza bus significativa ({round(float(b_rt), 1)}ms ➔ {round(float(t_rt), 1)}ms)",
                    ))

            status = DiffStatus.MODIFIED if changes else DiffStatus.UNCHANGED
            items.append(DeviceDiffItem(
                protocol="modbus",
                identifier=identifier,
                label=label,
                status=status,
                baseline_data=b_dev,
                target_data=t_dev,
                changes=changes,
            ))

    return items


def _compare_bacnet(
    base_devs: list[dict[str, Any]],
    target_devs: list[dict[str, Any]],
) -> list[DeviceDiffItem]:
    items: list[DeviceDiffItem] = []
    base_map = {d.get("device_id"): d for d in base_devs if d.get("device_id") is not None}
    target_map = {d.get("device_id"): d for d in target_devs if d.get("device_id") is not None}

    all_ids = sorted(set(base_map.keys()) | set(target_map.keys()))

    for dev_id in all_ids:
        in_base = dev_id in base_map
        in_target = dev_id in target_map
        b_dev = base_map.get(dev_id)
        t_dev = target_map.get(dev_id)

        sample = t_dev or b_dev
        vendor = sample.get("vendor_name") or f"Vendor #{sample.get('vendor_id', '?')}"
        model = sample.get("model_name") or "BACnet Device"
        address = sample.get("address", "")
        label = f"BACnet #{dev_id} – {vendor} {model} ({address})"
        identifier = f"Device #{dev_id}"

        if in_target and not in_base:
            items.append(DeviceDiffItem(
                protocol="bacnet",
                identifier=identifier,
                label=label,
                status=DiffStatus.ADDED,
                target_data=t_dev,
            ))
        elif in_base and not in_target:
            items.append(DeviceDiffItem(
                protocol="bacnet",
                identifier=identifier,
                label=label,
                status=DiffStatus.REMOVED,
                baseline_data=b_dev,
            ))
        else:
            changes: list[FieldChange] = []
            assert b_dev is not None and t_dev is not None

            for prop, desc in [
                ("address", "Indirizzo di rete/IP"),
                ("vendor_name", "Nome Costruttore"),
                ("model_name", "Modello Hardware"),
                ("firmware_revision", "Revisione Firmware"),
                ("application_software_version", "Versione Software Applicativo"),
            ]:
                if b_dev.get(prop) != t_dev.get(prop) and (b_dev.get(prop) or t_dev.get(prop)):
                    changes.append(FieldChange(
                        field=prop,
                        baseline=b_dev.get(prop),
                        target=t_dev.get(prop),
                        description=f"{desc} variato",
                    ))

            b_objs = len(b_dev.get("object_list") or [])
            t_objs = len(t_dev.get("object_list") or [])
            if b_objs != t_objs:
                changes.append(FieldChange(
                    field="object_list_count",
                    baseline=b_objs,
                    target=t_objs,
                    description=f"Oggetti BACnet censiti: {b_objs} ➔ {t_objs}",
                ))

            status = DiffStatus.MODIFIED if changes else DiffStatus.UNCHANGED
            items.append(DeviceDiffItem(
                protocol="bacnet",
                identifier=identifier,
                label=label,
                status=status,
                baseline_data=b_dev,
                target_data=t_dev,
                changes=changes,
            ))

    return items


def _compare_knx(
    base_devs: list[dict[str, Any]],
    target_devs: list[dict[str, Any]],
) -> list[DeviceDiffItem]:
    items: list[DeviceDiffItem] = []
    base_map = {_make_knx_key(d): d for d in base_devs}
    target_map = {_make_knx_key(d): d for d in target_devs}

    all_keys = sorted(set(base_map.keys()) | set(target_map.keys()))

    for key in all_keys:
        in_base = key in base_map
        in_target = key in target_map
        b_dev = base_map.get(key)
        t_dev = target_map.get(key)

        sample = t_dev or b_dev
        indiv = sample.get("individual_address", "?")
        dev_name = sample.get("device_name") or "KNXnet/IP Node"
        ip = sample.get("ip_address", "")
        label = f"KNX {indiv} – {dev_name} ({ip})"
        identifier = f"KNX {indiv}"

        if in_target and not in_base:
            items.append(DeviceDiffItem(
                protocol="knx",
                identifier=identifier,
                label=label,
                status=DiffStatus.ADDED,
                target_data=t_dev,
            ))
        elif in_base and not in_target:
            items.append(DeviceDiffItem(
                protocol="knx",
                identifier=identifier,
                label=label,
                status=DiffStatus.REMOVED,
                baseline_data=b_dev,
            ))
        else:
            changes: list[FieldChange] = []
            assert b_dev is not None and t_dev is not None

            for prop, desc in [
                ("ip_address", "Indirizzo IP Gateway KNX"),
                ("port", "Porta UDP"),
                ("device_name", "Nome Dispositivo"),
                ("serial_number", "Numero di Serie"),
                ("mac_address", "Indirizzo MAC"),
                ("medium", "Medium Fisico (TP1/IP/RF)"),
            ]:
                if b_dev.get(prop) != t_dev.get(prop) and (b_dev.get(prop) or t_dev.get(prop)):
                    changes.append(FieldChange(
                        field=prop,
                        baseline=b_dev.get(prop),
                        target=t_dev.get(prop),
                        description=f"{desc} variato",
                    ))

            status = DiffStatus.MODIFIED if changes else DiffStatus.UNCHANGED
            items.append(DeviceDiffItem(
                protocol="knx",
                identifier=identifier,
                label=label,
                status=status,
                baseline_data=b_dev,
                target_data=t_dev,
                changes=changes,
            ))

    return items


def _compare_ip_hosts(
    base_hosts: list[dict[str, Any]],
    target_hosts: list[dict[str, Any]],
) -> list[DeviceDiffItem]:
    items: list[DeviceDiffItem] = []

    # Mappatura intelligente per host IP:
    # 1. Match per MAC address se disponibile (identità fisica scheda)
    # 2. Match residuo per Indirizzo IP
    matched_target_indices: set[int] = set()
    matched_base_indices: set[int] = set()

    # Passata 1: match per MAC (non vuoto)
    base_by_mac: dict[str, int] = {}
    for i, h in enumerate(base_hosts):
        mac = (h.get("mac") or "").strip().upper()
        if mac and len(mac) >= 11:
            base_by_mac[mac] = i

    target_by_mac: dict[str, int] = {}
    for j, h in enumerate(target_hosts):
        mac = (h.get("mac") or "").strip().upper()
        if mac and len(mac) >= 11:
            target_by_mac[mac] = j

    common_macs = set(base_by_mac.keys()) & set(target_by_mac.keys())
    for mac in sorted(common_macs):
        b_idx = base_by_mac[mac]
        t_idx = target_by_mac[mac]
        matched_base_indices.add(b_idx)
        matched_target_indices.add(t_idx)

        b_h = base_hosts[b_idx]
        t_h = target_hosts[t_idx]
        ip = t_h.get("ip") or b_h.get("ip")
        hostname = t_h.get("hostname") or b_h.get("hostname") or ""
        label = f"Host {ip} [{mac}]" + (f" ({hostname})" if hostname else "")
        identifier = f"Host {ip}"

        changes: list[FieldChange] = []
        if b_h.get("ip") != t_h.get("ip"):
            changes.append(FieldChange(
                field="ip",
                baseline=b_h.get("ip"),
                target=t_h.get("ip"),
                description="Indirizzo IP riassegnato (DHCP o nuova configurazione)",
            ))
        if b_h.get("hostname") != t_h.get("hostname"):
            changes.append(FieldChange(
                field="hostname",
                baseline=b_h.get("hostname"),
                target=t_h.get("hostname"),
                description="Hostname variato",
            ))

        b_ports = sorted(b_h.get("open_ports") or [])
        t_ports = sorted(t_h.get("open_ports") or [])
        if b_ports != t_ports:
            changes.append(FieldChange(
                field="open_ports",
                baseline=b_ports,
                target=t_ports,
                description=f"Porte aperte variate: {b_ports} ➔ {t_ports}",
            ))

        status = DiffStatus.MODIFIED if changes else DiffStatus.UNCHANGED
        items.append(DeviceDiffItem(
            protocol="ip_host",
            identifier=identifier,
            label=label,
            status=status,
            baseline_data=b_h,
            target_data=t_h,
            changes=changes,
        ))

    # Passata 2: match per IP per i restanti
    base_by_ip: dict[str, int] = {}
    for i, h in enumerate(base_hosts):
        if i not in matched_base_indices:
            ip = (h.get("ip") or "").strip()
            if ip:
                base_by_ip[ip] = i

    target_by_ip: dict[str, int] = {}
    for j, h in enumerate(target_hosts):
        if j not in matched_target_indices:
            ip = (h.get("ip") or "").strip()
            if ip:
                target_by_ip[ip] = j

    common_ips = set(base_by_ip.keys()) & set(target_by_ip.keys())
    for ip in sorted(common_ips):
        b_idx = base_by_ip[ip]
        t_idx = target_by_ip[ip]
        matched_base_indices.add(b_idx)
        matched_target_indices.add(t_idx)

        b_h = base_hosts[b_idx]
        t_h = target_hosts[t_idx]
        mac = t_h.get("mac") or b_h.get("mac") or "—"
        hostname = t_h.get("hostname") or b_h.get("hostname") or ""
        label = f"Host {ip} [{mac}]" + (f" ({hostname})" if hostname else "")
        identifier = f"Host {ip}"

        changes: list[FieldChange] = []
        if (b_h.get("mac") or "").upper() != (t_h.get("mac") or "").upper():
            changes.append(FieldChange(
                field="mac",
                baseline=b_h.get("mac"),
                target=t_h.get("mac"),
                description="Indirizzo MAC variato (possibile sostituzione scheda di rete o apparato)",
            ))
        if b_h.get("hostname") != t_h.get("hostname"):
            changes.append(FieldChange(
                field="hostname",
                baseline=b_h.get("hostname"),
                target=t_h.get("hostname"),
                description="Hostname variato",
            ))

        b_ports = sorted(b_h.get("open_ports") or [])
        t_ports = sorted(t_h.get("open_ports") or [])
        if b_ports != t_ports:
            changes.append(FieldChange(
                field="open_ports",
                baseline=b_ports,
                target=t_ports,
                description=f"Porte aperte variate: {b_ports} ➔ {t_ports}",
            ))

        status = DiffStatus.MODIFIED if changes else DiffStatus.UNCHANGED
        items.append(DeviceDiffItem(
            protocol="ip_host",
            identifier=identifier,
            label=label,
            status=status,
            baseline_data=b_h,
            target_data=t_h,
            changes=changes,
        ))

    # Passata 3: rimanenti in target -> ADDED
    for j, t_h in enumerate(target_hosts):
        if j not in matched_target_indices:
            ip = t_h.get("ip") or "?"
            mac = t_h.get("mac") or "—"
            hostname = t_h.get("hostname") or ""
            label = f"Host {ip} [{mac}]" + (f" ({hostname})" if hostname else "")
            items.append(DeviceDiffItem(
                protocol="ip_host",
                identifier=f"Host {ip}",
                label=label,
                status=DiffStatus.ADDED,
                target_data=t_h,
            ))

    # Passata 4: rimanenti in baseline -> REMOVED
    for i, b_h in enumerate(base_hosts):
        if i not in matched_base_indices:
            ip = b_h.get("ip") or "?"
            mac = b_h.get("mac") or "—"
            hostname = b_h.get("hostname") or ""
            label = f"Host {ip} [{mac}]" + (f" ({hostname})" if hostname else "")
            items.append(DeviceDiffItem(
                protocol="ip_host",
                identifier=f"Host {ip}",
                label=label,
                status=DiffStatus.REMOVED,
                baseline_data=b_h,
            ))

    return items


def compare_snapshots(
    baseline_snapshot: dict[str, Any],
    target_snapshot: dict[str, Any],
    baseline_name: str = "Baseline",
    target_name: str = "Target",
) -> SessionDiffResult:
    """
    Esegue il confronto analitico completo tra due snapshot BHAM.
    """
    base_mb = [_to_dict(d) for d in baseline_snapshot.get("modbus_devices", [])]
    target_mb = [_to_dict(d) for d in target_snapshot.get("modbus_devices", [])]

    base_bn = [_to_dict(d) for d in baseline_snapshot.get("bacnet_devices", [])]
    target_bn = [_to_dict(d) for d in target_snapshot.get("bacnet_devices", [])]

    base_knx = [_to_dict(d) for d in baseline_snapshot.get("knx_devices", [])]
    target_knx = [_to_dict(d) for d in target_snapshot.get("knx_devices", [])]

    base_hosts = [_to_dict(d) for d in baseline_snapshot.get("ip_hosts", [])]
    target_hosts = [_to_dict(d) for d in target_snapshot.get("ip_hosts", [])]

    mb_items = _compare_modbus(base_mb, target_mb)
    bn_items = _compare_bacnet(base_bn, target_bn)
    knx_items = _compare_knx(base_knx, target_knx)
    host_items = _compare_ip_hosts(base_hosts, target_hosts)

    all_items = mb_items + bn_items + knx_items + host_items

    proto_groups = {
        "modbus": mb_items,
        "bacnet": bn_items,
        "knx": knx_items,
        "ip_host": host_items,
    }

    base_counts = {
        "modbus": len(base_mb),
        "bacnet": len(base_bn),
        "knx": len(base_knx),
        "ip_host": len(base_hosts),
    }

    target_counts = {
        "modbus": len(target_mb),
        "bacnet": len(target_bn),
        "knx": len(target_knx),
        "ip_host": len(target_hosts),
    }

    summary: dict[str, ProtocolDiffSummary] = {}
    tot_added = 0
    tot_removed = 0
    tot_modified = 0
    tot_unchanged = 0

    for proto, items in proto_groups.items():
        added = sum(1 for it in items if it.status == DiffStatus.ADDED)
        removed = sum(1 for it in items if it.status == DiffStatus.REMOVED)
        modified = sum(1 for it in items if it.status == DiffStatus.MODIFIED)
        unchanged = sum(1 for it in items if it.status == DiffStatus.UNCHANGED)

        tot_added += added
        tot_removed += removed
        tot_modified += modified
        tot_unchanged += unchanged

        summary[proto] = ProtocolDiffSummary(
            added=added,
            removed=removed,
            modified=modified,
            unchanged=unchanged,
            total_baseline=base_counts[proto],
            total_target=target_counts[proto],
        )

    summary["total"] = ProtocolDiffSummary(
        added=tot_added,
        removed=tot_removed,
        modified=tot_modified,
        unchanged=tot_unchanged,
        total_baseline=sum(base_counts.values()),
        total_target=sum(target_counts.values()),
    )

    status_priority = {
        DiffStatus.ADDED: 0,
        DiffStatus.REMOVED: 1,
        DiffStatus.MODIFIED: 2,
        DiffStatus.UNCHANGED: 3,
    }
    all_items.sort(key=lambda x: (status_priority.get(x.status, 9), x.protocol, x.identifier))

    log.info(
        "Confronto completato: %s vs %s – +%d aggiunti, -%d rimossi, ~%d modificati, =%d invariati",
        baseline_name,
        target_name,
        tot_added,
        tot_removed,
        tot_modified,
        tot_unchanged,
    )

    return SessionDiffResult(
        baseline_name=baseline_name,
        target_name=target_name,
        compared_at=utc_now(),
        summary=summary,
        items=all_items,
    )
