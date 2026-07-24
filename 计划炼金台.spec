# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

VERSION_FILE = str(Path(SPECPATH) / "version_info.txt")

APP_NAME = "计划炼金台"
ENTRY_SCRIPT = "main.py"
APP_ICON = "assets/icons/app_icon.ico"

def collect_resource_tree(source_dir, target_dir):
    source = Path(source_dir)
    entries = []
    for path in source.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            entries.append((str(path), str(Path(target_dir) / path.parent.relative_to(source))))
    return entries


datas = (
    [("assets/icons/app_icon.ico", "assets/icons")]
    + [("VERSION", ".")]
    + collect_resource_tree("assets/pictures", "assets/pictures")
)

hiddenimports = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

excludes = [
    "tkinter",
    "unittest",
    "pytest",
    "setuptools",
    "pip",
    "wheel",
    "matplotlib",
    "numpy",
    "pandas",
]

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=APP_ICON,
    version=VERSION_FILE,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
