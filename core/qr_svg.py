"""
BHAM – Lightweight Standalone QR Code SVG Generator
===================================================
Genera codici QR standard (Versioni 1-4, Livello Correzione Errore L)
in formato vettoriale SVG puro senza alcuna dipendenza binaria o pacchetto esterno.
Ideale per l'accesso mobile immediato alla console di cantiere LAN via smartphone/tablet.
"""

from __future__ import annotations

# Costruzione tabelle Galois Field GF(256) per Reed-Solomon
_EXP = [1] * 512
_LOG = [0] * 256
_x = 1
for _i in range(1, 255):
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
    _EXP[_i] = _x
    _LOG[_x] = _i
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gmul(x: int, y: int) -> int:
    return 0 if (x == 0 or y == 0) else _EXP[_LOG[x] + _LOG[y]]


def _rs_poly(n: int) -> list[int]:
    g = [1]
    for i in range(n):
        ng = [0] * (len(g) + 1)
        for j in range(len(g)):
            ng[j] ^= _gmul(g[j], _EXP[i])
            ng[j + 1] ^= g[j]
        g = ng
    return g


def _rs_encode(msg: list[int], ec_len: int) -> list[int]:
    poly = _rs_poly(ec_len)
    res = list(msg) + [0] * ec_len
    for i in range(len(msg)):
        coef = res[i]
        if coef != 0:
            for j in range(len(poly)):
                res[i + j] ^= _gmul(poly[len(poly) - 1 - j], coef)
    return res[len(msg):]


def generate_qr_svg(text: str, margin: int = 4, scale: int = 6, fill_color: str = "#0f172a") -> str:
    """
    Codifica un testo o URL in un codice QR SVG standard (v1..4).
    Restituisce la stringa XML dell'immagine SVG.
    """
    data = text.encode("iso-8859-1")
    length = len(data)

    if length <= 17:
        ver = 1
        data_cw = 19
        ec_cw = 7
        align: list[int] = []
    elif length <= 32:
        ver = 2
        data_cw = 34
        ec_cw = 10
        align = [18]
    elif length <= 53:
        ver = 3
        data_cw = 55
        ec_cw = 15
        align = [22]
    else:
        ver = 4
        data_cw = 80
        ec_cw = 20
        align = [26]

    # Bit stream: 4 bit Mode (0100 Byte) + 8 bit Conteggio + dati
    bits = [0, 1, 0, 0]
    for b in range(7, -1, -1):
        bits.append((length >> b) & 1)
    for byte in data:
        for b in range(7, -1, -1):
            bits.append((byte >> b) & 1)

    # Terminatore (fino a 4 zeri)
    term = min(4, data_cw * 8 - len(bits))
    bits.extend([0] * term)

    # Padding a confine di byte
    if len(bits) % 8 != 0:
        bits.extend([0] * (8 - (len(bits) % 8)))

    # Conversione in codewords
    codewords: list[int] = []
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        codewords.append(byte)

    # Padding fino a data_cw con 0xEC e 0x11
    pad_bytes = [0xEC, 0x11]
    p_idx = 0
    while len(codewords) < data_cw:
        codewords.append(pad_bytes[p_idx % 2])
        p_idx += 1

    # Calcolo codici Reed-Solomon
    ec_words = _rs_encode(codewords, ec_cw)
    all_cw = codewords + ec_words

    all_bits: list[int] = []
    for byte in all_cw:
        for b in range(7, -1, -1):
            all_bits.append((byte >> b) & 1)

    size = 17 + 4 * ver
    matrix = [[0] * size for _ in range(size)]
    reserved = [[False] * size for _ in range(size)]

    # 1. Finder patterns (tre angoli 7x7)
    def _finder(r: int, c: int) -> None:
        for dr in range(7):
            for dc in range(7):
                matrix[r + dr][c + dc] = 1 if (dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4)) else 0
                reserved[r + dr][c + dc] = True
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                nr, nc = r + dr, c + dc
                if 0 <= nr < size and 0 <= nc < size and not reserved[nr][nc]:
                    matrix[nr][nc] = 0
                    reserved[nr][nc] = True

    _finder(0, 0)
    _finder(0, size - 7)
    _finder(size - 7, 0)

    # 2. Alignment patterns
    for ar in align:
        for ac in align:
            if not reserved[ar][ac]:
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        matrix[ar + dr][ac + dc] = 1 if (abs(dr) == 2 or abs(dc) == 2 or (dr == 0 and dc == 0)) else 0
                        reserved[ar + dr][ac + dc] = True

    # 3. Timing patterns
    for i in range(size):
        if not reserved[6][i]:
            matrix[6][i] = 1 if i % 2 == 0 else 0
            reserved[6][i] = True
        if not reserved[i][6]:
            matrix[i][6] = 1 if i % 2 == 0 else 0
            reserved[i][6] = True

    # 4. Modulo scuro
    matrix[4 * ver + 9][8] = 1
    reserved[4 * ver + 9][8] = True

    # 5. Riserva format info
    for i in range(9):
        if not reserved[8][i]:
            reserved[8][i] = True
        if not reserved[i][8]:
            reserved[i][8] = True
    for i in range(size - 8, size):
        if not reserved[8][i]:
            reserved[8][i] = True
        if not reserved[i][8]:
            reserved[i][8] = True

    # 6. Posizionamento dati a zig-zag da destra a sinistra
    bit_idx = 0
    col = size - 1
    up = True
    while col > 0:
        if col == 6:
            col -= 1  # Salta colonna di timing
        rows = range(size - 1, -1, -1) if up else range(size)
        for r in rows:
            for c in (col, col - 1):
                if not reserved[r][c]:
                    b = all_bits[bit_idx] if bit_idx < len(all_bits) else 0
                    bit_idx += 1
                    # Applicazione Maschera standard 0: (r + c) % 2 == 0
                    if (r + c) % 2 == 0:
                        b ^= 1
                    matrix[r][c] = b
        up = not up
        col -= 2

    # 7. Format info (Livello L, Maschera 0): 0b010001111010110
    fmt = [0, 1, 0, 0, 0, 1, 1, 1, 1, 0, 1, 0, 1, 1, 0]
    for i in range(6):
        matrix[8][i] = fmt[i]
    matrix[8][7] = fmt[6]
    matrix[8][8] = fmt[7]
    matrix[7][8] = fmt[8]
    for i in range(6):
        matrix[5 - i][8] = fmt[9 + i]

    for i in range(8):
        matrix[8][size - 1 - i] = fmt[i]
    for i in range(7):
        matrix[size - 7 + i][8] = fmt[8 + i]

    # 8. Render in path SVG compatto
    dim = (size + 2 * margin) * scale
    svg_paths: list[str] = []
    for r in range(size):
        for c in range(size):
            if matrix[r][c]:
                x = (c + margin) * scale
                y = (r + margin) * scale
                svg_paths.append(f"M{x},{y}h{scale}v{scale}h-{scale}z")

    d = " ".join(svg_paths)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" width="{dim}" height="{dim}">'
        f'<rect width="100%" height="100%" fill="#ffffff" rx="8"/>'
        f'<path d="{d}" fill="{fill_color}"/>'
        f"</svg>"
    )
