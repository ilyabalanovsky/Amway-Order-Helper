# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import sys


PROJECT_DIR = Path(__file__).resolve().parent
ICON_ICO = PROJECT_DIR / "ui" / "amway.ico"
ICON_ICNS = PROJECT_DIR / "ui" / "amway.icns"

icon_path = None
if sys.platform == "darwin" and ICON_ICNS.exists():
    icon_path = str(ICON_ICNS)
elif ICON_ICO.exists():
    icon_path = str(ICON_ICO)

datas = []
if ICON_ICO.exists():
    datas.append((str(ICON_ICO), "ui"))
if ICON_ICNS.exists():
    datas.append((str(ICON_ICNS), "ui"))


a = Analysis(
    ["main.py"],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AmwayOrderHelper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
