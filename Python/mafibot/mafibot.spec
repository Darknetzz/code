# -*- mode: python ; coding: utf-8 -*-
"""Build: pyinstaller mafibot.spec  (from Python/mafibot, after playwright install)."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

spec_dir = Path(SPECPATH)

hiddenimports = [
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

a = Analysis(
    ["mafibot.py"],
    pathex=[str(spec_dir.parent / "webbot")],
    binaries=[],
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
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
