# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules("rich._unicode_data")
hiddenimports += collect_submodules("questionary")
hiddenimports += collect_submodules("prompt_toolkit")

# Global-site-packages leftovers PyInstaller must never pack into this CLI.
excludes = [
    "IPython",
    "PIL",
    "babel",
    "cryptography",
    "jedi",
    "llvmlite",
    "lxml",
    "matplotlib",
    "numba",
    "numpy",
    "pandas",
    "pyarrow",
    "pytest",
    "scipy",
    "sphinx",
    "tkinter",
]


def _drop_devel(entries):
    return [e for e in entries if "mupdf-devel" not in str(e).replace("\\", "/")]


a = Analysis(
    ["pyredact.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
a.binaries = _drop_devel(a.binaries)
a.datas = _drop_devel(a.datas)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="pyredact",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
