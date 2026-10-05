"""
BHAM – IEEE OUI Database & MAC Vendor Lookup
Provides manufacturer identification from MAC addresses with a curated
database focused on BACS, HVAC, PLC, industrial IoT, and networking vendors.
"""

from __future__ import annotations

import re
from typing import Optional

# Normalizzazione stringa MAC: estrae caratteri esadecimali
_MAC_HEX_RE = re.compile(r"^[0-9A-Fa-f]{2}[:-]?[0-9A-Fa-f]{2}[:-]?[0-9A-Fa-f]{2}")

# Database OUI (prefissi 24-bit IEEE / EUI-48 normalizzati a 6 cifre esadecimali maiuscole)
# Focus: BACS / BMS, HVAC, PLC, sensori IoT, controller e apparati di rete industriali
OUI_DATABASE: dict[str, str] = {
    # ── Schneider Electric & subsidiaries ───────────────────────────────────────
    "000054": "Schneider Electric",
    "0000E8": "Schneider Electric",
    "000EC6": "Schneider Electric",
    "0080F4": "Schneider Electric (Telemecanique)",
    "001854": "Schneider Electric",
    "001D43": "Schneider Electric",
    "002447": "Schneider Electric",
    "0025D3": "Schneider Electric",
    "00C067": "Schneider Electric",
    "5820B1": "Schneider Electric",
    "705681": "Schneider Electric",
    "E04F43": "Schneider Electric",
    "E47A23": "Schneider Electric",
    "F45433": "Schneider Electric",
    "00049F": "Schneider Electric (Feller AG)",
    "000B91": "Schneider Electric (TAC / Andover Controls)",
    "000C10": "Schneider Electric (TAC AB)",
    "000E08": "Schneider Electric (Invensys)",
    "00C0B7": "Schneider Electric (APC)",
    "000255": "Schneider Electric (APC)",

    # ── Siemens AG (Building Technologies & Industry) ──────────────────────────
    "000163": "Siemens AG",
    "000502": "Siemens AG",
    "000E8C": "Siemens AG",
    "001090": "Siemens AG",
    "00188B": "Siemens AG",
    "001C06": "Siemens AG",
    "001FBD": "Siemens AG",
    "0021A0": "Siemens AG",
    "00241B": "Siemens AG",
    "0026B0": "Siemens AG",
    "080006": "Siemens AG",
    "143004": "Siemens AG",
    "286336": "Siemens AG",
    "8CE748": "Siemens AG",
    "AC6417": "Siemens AG",
    "B0F893": "Siemens AG (Building Technologies / Desigo)",
    "BC9FE4": "Siemens AG",
    "C80AA9": "Siemens AG",
    "CCF954": "Siemens AG",
    "D09466": "Siemens AG",
    "E0DCFF": "Siemens AG",

    # ── Honeywell & Brands (Alerton, Trend, Centraline, Saia-Burgess) ───────────
    "000007": "Honeywell, Inc.",
    "0000C8": "Honeywell, Inc.",
    "000947": "Honeywell (Alerton)",
    "000E63": "Honeywell (Trend Controls)",
    "0010E0": "Honeywell / Trane",
    "004084": "Honeywell, Inc.",
    "006001": "Honeywell (Saia-Burgess Controls)",
    "00D02D": "Honeywell (Centraline / Novar)",
    "30894A": "Honeywell, Inc.",
    "F04B3A": "Honeywell, Inc.",

    # ── Johnson Controls (Metasys, Facility Explorer, Penn) ───────────────────
    "000760": "Johnson Controls",
    "00108D": "Johnson Controls",
    "0015A4": "Johnson Controls",
    "002148": "Johnson Controls",
    "00503E": "Johnson Controls",
    "006038": "Johnson Controls",
    "008066": "Johnson Controls",
    "00D009": "Johnson Controls",
    "188B9D": "Johnson Controls",
    "78A873": "Johnson Controls",

    # ── Carel Industries ──────────────────────────────────────────────────────
    "0004CD": "Carel Industries S.p.A.",
    "000B90": "Carel Industries S.p.A.",
    "0016B6": "Carel Industries S.p.A.",
    "00224C": "Carel Industries S.p.A.",
    "702C1F": "Carel Industries S.p.A.",

    # ── WAGO Kontakttechnik ───────────────────────────────────────────────────
    "0030DE": "WAGO Kontakttechnik GmbH",
    "70B3D5": "WAGO Kontakttechnik GmbH",

    # ── Beckhoff Automation ───────────────────────────────────────────────────
    "000105": "Beckhoff Automation GmbH",
    "000106": "Beckhoff Automation GmbH",
    "000107": "Beckhoff Automation GmbH",
    "003056": "Beckhoff Automation GmbH",

    # ── Moxa Inc. ─────────────────────────────────────────────────────────────
    "0090E8": "Moxa Inc.",
    "000A19": "Moxa Inc.",

    # ── Tridium Inc. (Niagara Framework / JACE) ───────────────────────────────
    "000EC3": "Tridium Inc.",
    "0050F1": "Tridium Inc. (JACE)",

    # ── Belimo Automation ─────────────────────────────────────────────────────
    "001CD2": "Belimo Automation AG",
    "0080A3": "Belimo Automation AG",

    # ── ABB & Busch-Jaeger / Cylon ────────────────────────────────────────────
    "000021": "ABB",
    "00024B": "ABB Busch-Jaeger",
    "000C02": "ABB Automation Technologies",
    "001B6B": "ABB Switzerland Ltd",
    "002409": "ABB",
    "005018": "ABB Cylon Controls",
    "74D02B": "ABB Stotz-Kontakt GmbH",

    # ── Carlo Gavazzi ─────────────────────────────────────────────────────────
    "0005C5": "Carlo Gavazzi Controls",
    "000BD7": "Carlo Gavazzi Controls",

    # ── Phoenix Contact ───────────────────────────────────────────────────────
    "00A045": "Phoenix Contact GmbH & Co. KG",
    "001B93": "Phoenix Contact GmbH & Co. KG",
    "00A0F4": "Phoenix Contact GmbH & Co. KG",

    # ── Danfoss ───────────────────────────────────────────────────────────────
    "0009B8": "Danfoss A/S",
    "001684": "Danfoss Drives",
    "001A8A": "Danfoss Power Electronics",

    # ── Omron ─────────────────────────────────────────────────────────────────
    "00000A": "Omron Corporation",
    "000034": "Omron Corporation",
    "000067": "Omron Corporation",
    "0000F4": "Omron Corporation",

    # ── Advantech ─────────────────────────────────────────────────────────────
    "000B7B": "Advantech Co., Ltd.",
    "001395": "Advantech Co., Ltd.",
    "00D0C9": "Advantech Co., Ltd.",
    "74FE48": "Advantech Co., Ltd.",

    # ── Sauter (Fr. Sauter AG) ────────────────────────────────────────────────
    "000201": "Fr. Sauter AG",
    "001D22": "Fr. Sauter AG",

    # ── Distech Controls ──────────────────────────────────────────────────────
    "00166C": "Distech Controls Inc.",
    "005096": "Distech Controls Inc.",

    # ── Regin AB ──────────────────────────────────────────────────────────────
    "000F4A": "AB Regin",
    "002195": "AB Regin",

    # ── Trane & American Standard ─────────────────────────────────────────────
    "000578": "Trane Technologies",
    "0015B7": "Trane Technologies",

    # ── Daikin ────────────────────────────────────────────────────────────────
    "000492": "Daikin Industries, Ltd.",
    "001693": "Daikin Europe N.V.",

    # ── Mitsubishi Electric ───────────────────────────────────────────────────
    "0000F0": "Mitsubishi Electric",
    "000E0C": "Mitsubishi Electric",
    "00152B": "Mitsubishi Electric",
    "001F00": "Mitsubishi Electric",

    # ── Rockwell Automation / Allen-Bradley ───────────────────────────────────
    "0000A7": "Rockwell Automation",
    "0000BC": "Rockwell Automation / Allen-Bradley",
    "001D9C": "Rockwell Automation",
    "008064": "Rockwell Automation",

    # ── Weidmüller ────────────────────────────────────────────────────
    "000FD2": "Weidmüller Interface GmbH",

    # ── Delta Controls ────────────────────────────────────────────────────────
    "000543": "Delta Controls Inc.",
    "001E31": "Delta Controls Inc.",

    # ── Loytec electronics ────────────────────────────────────────────────────
    "000A52": "LOYTEC electronics GmbH",
    "000F17": "LOYTEC electronics GmbH",

    # ── KMC Controls ──────────────────────────────────────────────────────────
    "000BB3": "KMC Controls, Inc.",

    # ── Contemporary Controls (CC) ────────────────────────────────────────────
    "00502A": "Contemporary Control Systems, Inc.",
    "000788": "Contemporary Control Systems, Inc.",

    # ── HMS Industrial Networks (Anybus, eWON, Ixxat) ──────────────────────────
    "0004A5": "HMS Industrial Networks (eWON)",
    "003011": "HMS Industrial Networks",
    "005046": "HMS Industrial Networks",

    # ── Westermo ──────────────────────────────────────────────────────────────
    "00077C": "Westermo Network Technologies",

    # ── Hirschmann / Belden ───────────────────────────────────────────────────
    "008063": "Hirschmann Automation and Control GmbH",
    "0017DA": "Belden Hirschmann",

    # ── Cisco Systems ─────────────────────────────────────────────────────────
    "00000C": "Cisco Systems, Inc.",
    "000142": "Cisco Systems, Inc.",
    "000196": "Cisco Systems, Inc.",
    "000216": "Cisco Systems, Inc.",
    "00044D": "Cisco Systems, Inc.",
    "000C85": "Cisco Systems, Inc.",
    "001D45": "Cisco Systems, Inc.",
    "0025B4": "Cisco Systems, Inc.",
    "F44E05": "Cisco Systems, Inc.",

    # ── MikroTik ──────────────────────────────────────────────────────────────
    "000C42": "MikroTik",
    "488F5A": "MikroTik",
    "64D154": "MikroTik",
    "789A18": "MikroTik",
    "B869F4": "MikroTik",
    "CC2DE0": "MikroTik",
    "D4CA6D": "MikroTik",

    # ── Ubiquiti ──────────────────────────────────────────────────────────────
    "00156D": "Ubiquiti Inc.",
    "002722": "Ubiquiti Inc.",
    "24A43C": "Ubiquiti Inc.",
    "68D79A": "Ubiquiti Inc.",
    "7483C2": "Ubiquiti Inc.",
    "B4FBE4": "Ubiquiti Inc.",
    "DC9FDB": "Ubiquiti Inc.",
    "F09FC2": "Ubiquiti Inc.",

    # ── IoT & Embedded SoC (Raspberry Pi, Espressif) ──────────────────────────
    "28CDC1": "Raspberry Pi Foundation",
    "B827EB": "Raspberry Pi Foundation",
    "DCA632": "Raspberry Pi Foundation",
    "E45F01": "Raspberry Pi Foundation",
    "D83ADD": "Raspberry Pi Foundation",
    "18FE34": "Espressif Systems (ESP8266/ESP32)",
    "240AC4": "Espressif Systems (ESP32)",
    "246F28": "Espressif Systems (ESP32)",
    "24B2DE": "Espressif Systems (ESP32)",
    "30AEA4": "Espressif Systems (ESP32)",
    "A4CF12": "Espressif Systems (ESP32)",
    "AC67B2": "Espressif Systems (ESP32)",
    "CC50E3": "Espressif Systems (ESP32)",

    # ── Common NICs & Virtualization (VMware, Intel, Realtek) ─────────────────
    "000569": "VMware, Inc.",
    "000C29": "VMware, Inc.",
    "001C14": "VMware, Inc.",
    "005056": "VMware, Inc.",
    "00155D": "Microsoft Hyper-V",
    "080027": "Oracle VirtualBox",
    "001A4B": "Hewlett Packard Enterprise",
    "001E67": "Intel Corporation",
    "00215A": "Intel Corporation",
    "001E8C": "Realtek Semiconductor Corp.",
    "00E04C": "Realtek Semiconductor Corp.",
}


def normalize_mac(mac: str) -> str:
    """
    Pulisce e normalizza un indirizzo MAC in formato standard 12 caratteri esadecimali maiuscoli
    oppure nei canonici 'XX:XX:XX:XX:XX:XX'.
    Rimuove separatori come :, -, ., spazi.
    """
    if not mac:
        return ""
    clean = re.sub(r"[^0-9A-Fa-f]", "", mac).upper()
    return clean


def format_mac_colon(mac: str) -> str:
    """Formatta un MAC come '00:11:22:33:44:55'."""
    clean = normalize_mac(mac)
    if len(clean) == 12:
        return ":".join(clean[i : i + 2] for i in range(0, 12, 2))
    return mac.strip()


def get_vendor_by_mac(mac: str) -> Optional[str]:
    """
    Ritorna il produttore associato all'indirizzo MAC interrogando il database OUI.
    Accetta formati come:
      - '00:1C:06:12:34:56'
      - '00-1c-06-12-34-56'
      - '001c.0612.3456'
      - '001C06' (prefisso 24-bit)

    Ritorna None se il prefisso OUI non è presente nel database.
    """
    if not mac:
        return None
    clean = normalize_mac(mac)
    if len(clean) < 6:
        return None
    prefix = clean[:6]
    return OUI_DATABASE.get(prefix)
