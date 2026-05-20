"""PyInstaller runtime hook: Playwright bundled browsers inside the frozen bundle."""

import os
import sys

if getattr(sys, "frozen", False):
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
