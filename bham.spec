# -*- mode: python ; coding: utf-8 -*-
"""
BHAM – PyInstaller Spec File
Builds standalone single-binary executable for field commissioning.
Usage:
    pyinstaller bham.spec
"""

import sys
from pathlib import Path

block_cipher = None

# Bundle frontend assets
datas = [
    ('frontend', 'frontend'),
]

# Ensure dynamic imports and protocols are captured
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.wsproto_impl',
    'scapy.layers.l2',
    'scapy.layers.inet',
    'bacpypes3',
    'bacpypes3.ipv4',
    'bacpypes3.apdu',
    'pymodbus',
    'pymodbus.client',
    'reportlab',
    'reportlab.platypus',
    'reportlab.pdfgen.canvas',
    'openpyxl',
    'psutil',
    'serial',
    'aiofiles',
    'scanners.knx',
    'scanners.serial_sniffer',
    'core.priv_check',
    'core.session_diff',
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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
