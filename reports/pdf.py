"""
BHAM – PDF Report Generator (Production Styled)
Genera report PDF completo con stile industriale per collaudi BACS:
- Copertina con dettagli sessione / sito cliente e sommario dispositivi
- Tabelle stilizzate e color-coded per protocollo (Modbus, BACnet, IP/ARP)
- Paginazione automatica (Pagina X di Y) e intestazione
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import warnings

# ReportLab 4.2.5 triggers DeprecationWarning for ast.NameConstant on Python 3.12+
warnings.filterwarnings("ignore", category=DeprecationWarning, message=r".*NameConstant.*")

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from data.state import state


class NumberedCanvas(canvas.Canvas):
    """Canvas personalizzato a due passate per calcolo e stampa del totale pagine."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for page_state in self._saved_page_states:
            self.__dict__.update(page_state)
            self._draw_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_decorations(self, total_pages: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Header visibile solo dalla pagina 2 in poi
        if self._pageNumber > 1:
            self.drawString(40, 812, "BHAM – BACS Discovery Report")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(40, 804, 555, 804)

        # Footer su tutte le pagine
        self.drawString(40, 28, "BACS Help Auto Mapper – Documento di Collaudo")
        page_str = f"Pagina {self._pageNumber} di {total_pages}"
        self.drawRightString(555, 28, page_str)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(40, 38, 555, 38)

        self.restoreState()


def generate_pdf(filepath: str) -> str:
    """
    Genera un report PDF di collaudo BACS a partire dallo stato corrente.
    Ritorna il path assoluto del file generato.
    """
    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=50,
        bottomMargin=50,
    )

    base_styles = getSampleStyleSheet()

    # ── Stili Tipografici ────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=base_styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#0F172A"),
        alignment=0,
    )

    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0284C7"),
        alignment=0,
    )

    h2_style = ParagraphStyle(
        "SectionH2",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=12,
        spaceAfter=6,
    )

    meta_label_style = ParagraphStyle(
        "MetaLabel",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )

    meta_val_style = ParagraphStyle(
        "MetaVal",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0F172A"),
    )

    tbl_hdr_style = ParagraphStyle(
        "TableHdr",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1,
    )

    tbl_cell_style = ParagraphStyle(
        "TableCell",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0F172A"),
    )

    tbl_cell_center = ParagraphStyle(
        "TableCellCenter",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0F172A"),
        alignment=1,
    )

    tbl_cell_bold = ParagraphStyle(
        "TableCellBold",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0F172A"),
        alignment=1,
    )

    elements: list[Any] = []

    # ── Header Documento / Cover Block ───────────────────────────────────────
    elements.append(Paragraph("⚡ BHAM – BACS Discovery Report", title_style))
    elements.append(Paragraph("Automated Commissioning & Network Topology Inspection", subtitle_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceAfter=14))

    # Metadati Sessione
    cfg = state.session_config
    site_name = (cfg.site_name if cfg and cfg.site_name else "Impianto non specificato")
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    meta_table_data = [
        [
            Paragraph("Sito / Impianto:", meta_label_style),
            Paragraph(site_name, meta_val_style),
            Paragraph("Data Generazione:", meta_label_style),
            Paragraph(now_str, meta_val_style),
        ],
        [
            Paragraph("Porta Seriale RS485:", meta_label_style),
            Paragraph(f"{cfg.serial_port or 'Non configurata'} ({cfg.serial_baudrate if cfg else 9600} bps)" if cfg else "—", meta_val_style),
            Paragraph("NIC Scansione Rete:", meta_label_style),
            Paragraph(f"{cfg.scan_iface or 'Auto'} ({cfg.scan_ip or '—'})" if cfg else "—", meta_val_style),
        ],
    ]
    meta_table = Table(meta_table_data, colWidths=[110, 150, 105, 150])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 14))

    # ── Sintesi Dispositivi Rilevati (Summary Box) ───────────────────────────
    mb_count = len(state.modbus_devices)
    bn_count = len(state.bacnet_devices)
    knx_count = len(state.knx_devices)
    ip_count = len(state.ip_hosts)

    summary_data = [
        [
            Paragraph("<b>Modbus</b>", meta_label_style),
            Paragraph(f"<b>{mb_count}</b>", meta_val_style),
            Paragraph("<b>BACnet/IP</b>", meta_label_style),
            Paragraph(f"<b>{bn_count}</b>", meta_val_style),
            Paragraph("<b>KNXnet/IP</b>", meta_label_style),
            Paragraph(f"<b>{knx_count}</b>", meta_val_style),
            Paragraph("<b>Host ARP</b>", meta_label_style),
            Paragraph(f"<b>{ip_count}</b>", meta_val_style),
        ]
    ]
    summary_table = Table(summary_data, colWidths=[85, 35, 95, 35, 95, 35, 95, 40])
    summary_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (3, 0), (3, 0), "CENTER"),
        ("ALIGN", (5, 0), (5, 0), "CENTER"),
        ("ALIGN", (7, 0), (7, 0), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#0284C7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 16))

    # ── 1. Tabella Modbus ────────────────────────────────────────────────────
    elements.append(Paragraph(f"1. Dispositivi Modbus ({mb_count})", h2_style))
    if mb_count == 0:
        elements.append(Paragraph("<i>Nessun dispositivo Modbus rilevato.</i>", tbl_cell_style))
    else:
        mb_headers = [
            Paragraph("Slave ID", tbl_hdr_style),
            Paragraph("Protocollo", tbl_hdr_style),
            Paragraph("Endpoint / Porta", tbl_hdr_style),
            Paragraph("Tempo Risposta", tbl_hdr_style),
            Paragraph("Costruttore / Modello", tbl_hdr_style),
        ]
        mb_rows = [mb_headers]
        for d in sorted(state.modbus_devices.values(), key=lambda x: x.slave_id):
            endpoint = d.ip if d.ip else (d.serial_params.port if d.serial_params else "—")
            if d.ip and d.tcp_port:
                endpoint = f"{d.ip}:{d.tcp_port}"
            resp_ms = f"{d.response_time_ms:.1f} ms" if d.response_time_ms else "—"
            vendor_model = " / ".join(filter(None, [getattr(d, "vendor_name", None), getattr(d, "model_name", None)])) or "—"

            mb_rows.append([
                Paragraph(str(d.slave_id), tbl_cell_bold),
                Paragraph(d.protocol.value.replace("_", " ").upper(), tbl_cell_center),
                Paragraph(endpoint, tbl_cell_style),
                Paragraph(resp_ms, tbl_cell_center),
                Paragraph(vendor_model, tbl_cell_style),
            ])

        col_w = [55, 80, 140, 75, 165]
        t_mb = Table(mb_rows, colWidths=col_w, repeatRows=1)
        t_mb_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0284C7")),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for i in range(1, len(mb_rows)):
            if i % 2 == 0:
                t_mb_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F1F5F9")))
        t_mb.setStyle(TableStyle(t_mb_style))
        elements.append(t_mb)

    elements.append(Spacer(1, 16))

    # ── 2. Tabella BACnet ────────────────────────────────────────────────────
    elements.append(Paragraph(f"2. Dispositivi BACnet/IP ({bn_count})", h2_style))
    if bn_count == 0:
        elements.append(Paragraph("<i>Nessun dispositivo BACnet rilevato.</i>", tbl_cell_style))
    else:
        bn_headers = [
            Paragraph("Device ID", tbl_hdr_style),
            Paragraph("Indirizzo", tbl_hdr_style),
            Paragraph("Costruttore", tbl_hdr_style),
            Paragraph("Modello", tbl_hdr_style),
            Paragraph("Revisione FW", tbl_hdr_style),
        ]
        bn_rows = [bn_headers]
        for d in sorted(state.bacnet_devices.values(), key=lambda x: x.device_id):
            bn_rows.append([
                Paragraph(str(d.device_id), tbl_cell_bold),
                Paragraph(d.address, tbl_cell_style),
                Paragraph(d.vendor_name or "—", tbl_cell_style),
                Paragraph(d.model_name or "—", tbl_cell_style),
                Paragraph(d.firmware_revision or "—", tbl_cell_center),
            ])

        col_w = [65, 110, 125, 130, 85]
        t_bn = Table(bn_rows, colWidths=col_w, repeatRows=1)
        t_bn_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7C3AED")),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for i in range(1, len(bn_rows)):
            if i % 2 == 0:
                t_bn_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5F3FF")))
        t_bn.setStyle(TableStyle(t_bn_style))
        elements.append(t_bn)

    elements.append(Spacer(1, 16))

    # ── 3. Tabella KNXnet/IP ─────────────────────────────────────────────────
    elements.append(Paragraph(f"3. Dispositivi KNXnet/IP ({knx_count})", h2_style))
    if knx_count == 0:
        elements.append(Paragraph("<i>Nessun dispositivo KNXnet/IP rilevato.</i>", tbl_cell_style))
    else:
        knx_headers = [
            Paragraph("Indirizzo Indiv.", tbl_hdr_style),
            Paragraph("IP / Porta", tbl_hdr_style),
            Paragraph("Nome Dispositivo", tbl_hdr_style),
            Paragraph("Numero Serie", tbl_hdr_style),
            Paragraph("Medium", tbl_hdr_style),
        ]
        knx_rows = [knx_headers]
        for k in sorted(state.knx_devices.values(), key=lambda x: x.individual_address):
            knx_rows.append([
                Paragraph(k.individual_address, tbl_cell_bold),
                Paragraph(f"{k.ip_address}:{k.port}", tbl_cell_center),
                Paragraph(k.device_name or "—", tbl_cell_style),
                Paragraph(k.serial_number or "—", tbl_cell_center),
                Paragraph(k.medium, tbl_cell_center),
            ])

        col_w = [85, 115, 150, 110, 55]
        t_knx = Table(knx_rows, colWidths=col_w, repeatRows=1)
        t_knx_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C2410C")),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for i in range(1, len(knx_rows)):
            if i % 2 == 0:
                t_knx_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FFF7ED")))
        t_knx.setStyle(TableStyle(t_knx_style))
        elements.append(t_knx)

    elements.append(Spacer(1, 16))

    # ── 4. Tabella IP Hosts (ARP) ────────────────────────────────────────────
    elements.append(Paragraph(f"4. Host di Rete Rilevati ({ip_count})", h2_style))
    if ip_count == 0:
        elements.append(Paragraph("<i>Nessun host rilevato tramite sniffing ARP.</i>", tbl_cell_style))
    else:
        ip_headers = [
            Paragraph("Indirizzo IP", tbl_hdr_style),
            Paragraph("Indirizzo MAC", tbl_hdr_style),
            Paragraph("Hostname", tbl_hdr_style),
            Paragraph("Primo Rilevamento", tbl_hdr_style),
        ]
        ip_rows = [ip_headers]
        for h in sorted(state.ip_hosts.values(), key=lambda x: x.ip):
            first_seen_str = str(h.first_seen)[:19] if h.first_seen else "—"
            ip_rows.append([
                Paragraph(h.ip, tbl_cell_bold),
                Paragraph(h.mac or "—", tbl_cell_center),
                Paragraph(h.hostname or "—", tbl_cell_style),
                Paragraph(first_seen_str, tbl_cell_center),
            ])

        col_w = [110, 130, 140, 135]
        t_ip = Table(ip_rows, colWidths=col_w, repeatRows=1)
        t_ip_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#059669")),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for i in range(1, len(ip_rows)):
            if i % 2 == 0:
                t_ip_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#ECFDF5")))
        t_ip.setStyle(TableStyle(t_ip_style))
        elements.append(t_ip)

    elements.append(Spacer(1, 16))

    # ── 5. Mappa Topologica Gerarchica ───────────────────────────────────────
    topo = state.get_topology()
    topo_nodes = topo.get("nodes", [])
    elements.append(Paragraph(f"5. Mappa Topologica Gerarchica d'Impianto ({len(topo_nodes)} nodi)", h2_style))

    nodes_by_id = {n["id"]: n for n in topo_nodes}
    children_map: dict[str, list[str]] = {}
    for n in topo_nodes:
        parent = n.get("parent_id")
        if parent:
            children_map.setdefault(parent, []).append(n["id"])

    def _walk_tree(nid: str, depth: int = 0) -> list[tuple[dict, int]]:
        node = nodes_by_id.get(nid)
        if not node:
            return []
        res = [(node, depth)]
        for cid in children_map.get(nid, []):
            res.extend(_walk_tree(cid, depth + 1))
        return res

    tree_walk = _walk_tree("node:host", 0)
    visited_ids = {node["id"] for node, _ in tree_walk}
    for n in topo_nodes:
        if n["id"] not in visited_ids:
            tree_walk.append((n, 1))

    topo_headers = [
        Paragraph("Albero d'Impianto / Nodo", tbl_hdr_style),
        Paragraph("Livello", tbl_hdr_style),
        Paragraph("Protocollo", tbl_hdr_style),
        Paragraph("Stato", tbl_hdr_style),
    ]
    topo_rows = [topo_headers]
    level_names = {"host": "1: Host", "interface": "2: Canale", "bus": "3: Bus", "device": "4: Nodo"}

    for n, depth in tree_walk:
        indent = "&nbsp;" * (depth * 5)
        prefix = "• " if depth >= 3 else ("└─ " if depth == 2 else ("├─ " if depth == 1 else "🖥️ "))
        sub = f" <font color='#64748B'>({n.get('sublabel')})</font>" if n.get("sublabel") else ""
        label_html = f"{indent}{prefix}<b>{n.get('label', '')}</b>{sub}"

        cat = n.get("category", "device")
        lvl_str = level_names.get(cat, f"Lvl {depth}")
        proto_str = n.get("protocol", "").upper()
        status_str = n.get("status", "unknown").upper()

        topo_rows.append([
            Paragraph(label_html, tbl_cell_style),
            Paragraph(lvl_str, tbl_cell_center),
            Paragraph(proto_str, tbl_cell_center),
            Paragraph(status_str, tbl_cell_center),
        ])

    col_w_topo = [240, 85, 105, 85]
    t_topo = Table(topo_rows, colWidths=col_w_topo, repeatRows=1)
    t_topo_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(1, len(topo_rows)):
        if i % 2 == 0:
            t_topo_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F8FAFC")))
    t_topo.setStyle(TableStyle(t_topo_style))
    elements.append(t_topo)

    # ── 6. As-Built Modbus Registers ─────────────────────────────────────────
    total_modbus_regs = sum(len(d.registers) for d in state.modbus_devices.values() if d.registers)
    if total_modbus_regs > 0:
        elements.append(Spacer(1, 16))
        elements.append(Paragraph(f"6. As-Built – Censimento Registri Modbus ({total_modbus_regs} registri)", h2_style))
        reg_headers = [
            Paragraph("Slave ID", tbl_hdr_style),
            Paragraph("Canale", tbl_hdr_style),
            Paragraph("Registro", tbl_hdr_style),
            Paragraph("Raw Hex", tbl_hdr_style),
            Paragraph("Dec Int16", tbl_hdr_style),
            Paragraph("Float32", tbl_hdr_style),
            Paragraph("Etichetta / Tag", tbl_hdr_style),
        ]
        reg_rows = [reg_headers]
        for d in sorted(state.modbus_devices.values(), key=lambda x: x.slave_id):
            endpoint = d.ip if d.ip else (d.serial_params.port if d.serial_params else "RS485")
            if d.ip and d.tcp_port:
                endpoint = f"{d.ip}:{d.tcp_port}"
            if d.registers:
                for reg_addr, rdata in sorted(d.registers.items(), key=lambda x: str(x[0])):
                    if isinstance(rdata, dict):
                        hex_val = rdata.get("hex", "")
                        dec_val = rdata.get("int16", rdata.get("dec", ""))
                        float_val = rdata.get("float32", "")
                        desc = rdata.get("description", rdata.get("label", ""))
                    else:
                        hex_val = hex(rdata) if isinstance(rdata, int) else ""
                        dec_val = str(rdata)
                        float_val = ""
                        desc = ""
                    reg_rows.append([
                        Paragraph(str(d.slave_id), tbl_cell_bold),
                        Paragraph(endpoint, tbl_cell_style),
                        Paragraph(str(reg_addr), tbl_cell_center),
                        Paragraph(str(hex_val), tbl_cell_center),
                        Paragraph(str(dec_val), tbl_cell_center),
                        Paragraph(str(float_val), tbl_cell_center),
                        Paragraph(str(desc) or "—", tbl_cell_style),
                    ])
        col_w_reg = [45, 95, 60, 65, 65, 80, 105]
        t_regs = Table(reg_rows, colWidths=col_w_reg, repeatRows=1)
        t_regs_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#B45309")),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for i in range(1, len(reg_rows)):
            if i % 2 == 0:
                t_regs_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FFFBEB")))
        t_regs.setStyle(TableStyle(t_regs_style))
        elements.append(t_regs)

    # ── 7. As-Built BACnet Objects Explorer ──────────────────────────────────
    total_bacnet_objs = sum(len(d.object_list) for d in state.bacnet_devices.values() if d.object_list)
    if total_bacnet_objs > 0:
        elements.append(Spacer(1, 16))
        elements.append(Paragraph(f"7. As-Built – Censimento Oggetti BACnet ({total_bacnet_objs} oggetti)", h2_style))
        obj_headers = [
            Paragraph("Device ID", tbl_hdr_style),
            Paragraph("Tipo", tbl_hdr_style),
            Paragraph("ID Oggetto", tbl_hdr_style),
            Paragraph("Nome Oggetto", tbl_hdr_style),
            Paragraph("Valore", tbl_hdr_style),
            Paragraph("Unità", tbl_hdr_style),
        ]
        obj_rows = [obj_headers]
        for d in sorted(state.bacnet_devices.values(), key=lambda x: x.device_id):
            if d.object_list:
                for obj in d.object_list:
                    obj_id = obj.get("object_identifier") or obj.get("id", "")
                    obj_type = obj.get("object_type") or obj.get("type", "")
                    obj_name = obj.get("object_name") or obj.get("name", "")
                    pval = obj.get("present_value")
                    pval_str = str(pval) if pval is not None else "—"
                    units = obj.get("units", "—")
                    obj_rows.append([
                        Paragraph(str(d.device_id), tbl_cell_bold),
                        Paragraph(str(obj_type), tbl_cell_center),
                        Paragraph(str(obj_id), tbl_cell_style),
                        Paragraph(str(obj_name), tbl_cell_style),
                        Paragraph(pval_str, tbl_cell_center),
                        Paragraph(str(units) or "—", tbl_cell_center),
                    ])
        col_w_obj = [55, 75, 85, 155, 85, 60]
        t_objs = Table(obj_rows, colWidths=col_w_obj, repeatRows=1)
        t_objs_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4338CA")),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for i in range(1, len(obj_rows)):
            if i % 2 == 0:
                t_objs_style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#EEF2FF")))
        t_objs.setStyle(TableStyle(t_objs_style))
        elements.append(t_objs)

    # Compilazione documento con il canvas personalizzato
    doc.build(elements, canvasmaker=NumberedCanvas)
    return filepath

