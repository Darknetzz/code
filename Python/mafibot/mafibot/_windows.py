"""Windows-only helpers (load MSVC DLLs before greenlet/playwright)."""

from __future__ import annotations

import sys


def ensure_msvc_runtime() -> None:
    """Load msvc-runtime DLLs so greenlet's _greenlet.pyd can import on Windows."""
    if sys.platform != "win32":
        return
    try:
        import msvc_runtime  # noqa: F401
    except ImportError:
        pass
