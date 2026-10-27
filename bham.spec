# -*- mode: python ; coding: utf-8 -*-
"""
BHAM – PyInstaller Spec File
Builds standalone single-binary executable for field commissioning.
Usage:
    pyinstaller bham.spec

Note Windows:
  - il manifest applicativo (UAC asInvoker + DPI awareness) viene generato a
    partire da bham.exe.manifest iniettando la versione corrente;
  - viene incorporata la risorsa VERSIONINFO, indispensabile perché SmartScreen
    e gli antivirus riconoscano l'eseguibile come prodotto identificabile;
  - UPX è disattivato: la compressione corrompe alcune DLL del runtime Python
    e genera falsi positivi antivirus sui binari onefile.
"""

import re
import sys
from pathlib import Path

block_cipher = None

SPEC_ROOT = Path(SPECPATH).resolve()
IS_WINDOWS = sys.platform == "win32"
BUILD_AUX = SPEC_ROOT / "build" / "winres"


def _read_version() -> str:
    """Legge la versione canonica da pyproject.toml (unica fonte di verità)."""
    text = (SPEC_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else "0.0.0"


APP_VERSION = _read_version()
_parts = (APP_VERSION.split("+")[0].split("-")[0].split("."), )[0]
VERSION_TUPLE = tuple(int(p) if p.isdigit() else 0 for p in (_parts + ["0", "0", "0", "0"])[:4])


def _write_windows_resources() -> tuple[str | None, str | None]:
    """
    Genera in build/winres il file VERSIONINFO e il manifest con la versione
    corrente. Ritorna (version_file, manifest_file) o (None, None) fuori Windows.
    """
    if not IS_WINDOWS:
        return None, None

    BUILD_AUX.mkdir(parents=True, exist_ok=True)
    dotted = ", ".join(str(n) for n in VERSION_TUPLE)

    version_file = BUILD_AUX / "bham_version_info.txt"
    version_file.write_text(
        "VSVersionInfo(\n"
        "  ffi=FixedFileInfo(\n"
        f"    filevers=({dotted}),\n"
        f"    prodvers=({dotted}),\n"
        "    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)\n"
        "  ),\n"
        "  kids=[\n"
        "    StringFileInfo([StringTable('040904B0', [\n"
        "      StringStruct('CompanyName', 'BACS Help'),\n"
        "      StringStruct('FileDescription', 'BHAM - BACS Help Auto Mapper'),\n"
        f"      StringStruct('FileVersion', '{APP_VERSION}'),\n"
        "      StringStruct('InternalName', 'bham'),\n"
        "      StringStruct('LegalCopyright', 'Copyright (c) 2026 BACS Help - MIT License'),\n"
        "      StringStruct('OriginalFilename', 'bham.exe'),\n"
        "      StringStruct('ProductName', 'BHAM - BACS Help Auto Mapper'),\n"
        f"      StringStruct('ProductVersion', '{APP_VERSION}'),\n"
        "    ])]),\n"
        "    VarFileInfo([VarStruct('Translation', [1033, 1200])])\n"
        "  ]\n"
        ")\n",
        encoding="utf-8",
    )

    manifest_src = SPEC_ROOT / "bham.exe.manifest"
    manifest_file = None
    if manifest_src.exists():
        manifest_xml = manifest_src.read_text(encoding="utf-8")
        manifest_xml = re.sub(
            r'(version=")\d+\.\d+\.\d+\.\d+(")',
            rf'\g<1>{".".join(str(n) for n in VERSION_TUPLE)}\g<2>',
            manifest_xml,
            count=1,
        )
        manifest_file = BUILD_AUX / "bham.exe.manifest"
        manifest_file.write_text(manifest_xml, encoding="utf-8")

    return str(version_file), str(manifest_file) if manifest_file else None


WIN_VERSION_FILE, WIN_MANIFEST_FILE = _write_windows_resources()

# Bundle frontend assets and builtin device profiles
datas = [
    ('frontend', 'frontend'),
    ('profiles/builtin', 'profiles/builtin'),
]

# Ensure dynamic imports and protocols are captured
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    # Implementazione sans-io introdotta da uvicorn recente: `--ws auto` la
    # seleziona al posto di quella legacy.
    'uvicorn.protocols.websockets.websockets_sansio_impl',
    'h11',
    'websockets',
    'websockets.asyncio',
    # NOTA: `wsproto` non è più una dipendenza di uvicorn[standard], quindi
    # `wsproto_impl` non è importabile: elencarli produceva solo un avviso di
    # hiddenimport mancante a ogni build.
    'websockets.legacy',
    'scapy.layers.l2',
    'scapy.layers.inet',
    'bacpypes3',
    'bacpypes3.ipv4',
    'bacpypes3.apdu',
    'pymodbus',
    'pymodbus.client',
    # Da pymodbus 3.16 la richiesta FC43 vive sotto pymodbus.pdu: l'import è
    # tardivo, quindi va dichiarato perché finisca nel bundle.
    'pymodbus.pdu',
    'pymodbus.pdu.mei_message',
    'reportlab',
    'reportlab.platypus',
    'reportlab.pdfgen.canvas',
    'openpyxl',
    'psutil',
    'serial',
    'serial.tools.list_ports',
    'aiofiles',
    'scanners.knx',
    'scanners.serial_sniffer',
    'core.paths',
    'core.priv_check',
    'core.browser',
    'core.preflight',
    'core.system_requirements',
    'core.session_diff',
    'core.simulator',
    'core.audit_journal',
    'core.safe_mode',
    'core.profile_manager',
    'core.oui_lookup',
    'core.qr_svg',
    'core.tag_exporter',
    'scanners.field_tools',
    'scanners.ip_scanner',
    'api.schemas',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='bham',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True if sys.platform.startswith('linux') else False,
    # UPX disattivato: corrompe le DLL del runtime Python su Windows e fa
    # scattare falsi positivi negli antivirus, bloccando l'installazione.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=WIN_VERSION_FILE,
    manifest=WIN_MANIFEST_FILE,
)
