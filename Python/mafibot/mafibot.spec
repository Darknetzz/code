# -*- mode: python ; coding: utf-8 -*-
"""Build: pyinstaller mafibot.spec  (from Python/mafibot, after playwright install)."""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

spec_dir = Path(SPECPATH)

binaries = []
hiddenimports = [
    "greenlet",
    "greenlet._greenlet",
    "webbot",
    "webbot.browser",
    "webbot.human",
    "webbot.locators",
    "webbot.run_context",
    "mafibot.server",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "pydantic",
    "playwright",
    "playwright.async_api",
]
hiddenimports += collect_submodules("rich._unicode_data")

datas = [
    (str(spec_dir / "mafibot" / "static"), "mafibot/static"),
    (str(spec_dir / "mafibot" / "profiles"), "mafibot/profiles"),
]
datas += collect_data_files("playwright", include_py_files=False)

# Playwright imports greenlet; on Windows the .pyd needs MSVC runtime DLLs in the bundle.
_g_datas, _g_bins, _g_hidden = collect_all("greenlet")
datas += _g_datas
binaries += _g_bins
hiddenimports += _g_hidden

if sys.platform == "win32":
    try:
        import msvc_runtime
    except ImportError as exc:
        raise SystemExit(
            "Windows build requires msvc-runtime (pip install msvc-runtime). "
            "It bundles VC++ DLLs needed by greenlet/Playwright in the frozen exe."
        ) from exc
    msvc_dir = Path(msvc_runtime.__file__).resolve().parent
    for dll in msvc_dir.glob("*.dll"):
        binaries.append((str(dll), "."))

a = Analysis(
    ["mafibot.py"],
    pathex=[str(spec_dir.parent / "webbot")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(spec_dir / "pyi_rth_mafibot.py")],
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
    name="mafibot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=["_greenlet.pyd"],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
