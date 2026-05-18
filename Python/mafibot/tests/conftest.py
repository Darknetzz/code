"""Test path setup for webbot + mafibot."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBBOT = ROOT.parent / "webbot"
for p in (ROOT, WEBBOT):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)
