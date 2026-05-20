"""Paths and env for PyInstaller-frozen (single-file) builds."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """Directory containing packaged mafibot package assets (static, profiles)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path.cwd()))
    return Path(__file__).resolve().parent


def configure_frozen_env() -> None:
    """Playwright: use browsers bundled next to the driver inside the frozen bundle."""
    if is_frozen():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
