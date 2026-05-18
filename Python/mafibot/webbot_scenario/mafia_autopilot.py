"""
Webbot Python scenario: Mafiaspillet autopilot.

Install: python mafibot.py install-webbot-scenario
Run: cd Python/webbot && python webbot.py run mafia_autopilot
Requires: mafibot login first; pass --accept-tos via env MAFIBOT_ACCEPT_TOS=1 not supported — use mafibot run instead.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_MAFIBOT = Path(r"{{MAFIBOT_REPO}}")
_WEBBOT = _MAFIBOT.parent / "webbot"
for p in (_MAFIBOT, _WEBBOT):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from playwright.async_api import Page

from mafibot.brain import run_forever
from mafibot.config import load_bot_profile

DESCRIPTION = "Mafiaspillet autopilot (requires mafibot login + --accept-tos via mafibot CLI)"
STEP_LABELS = ("autopilot loop",)


async def run(page: Page) -> None:
    profile_name = os.getenv("MAFIBOT_PROFILE", "ranker")
    profile = load_bot_profile(profile_name)
    await run_forever(page, profile, max_minutes=profile.max_session_minutes, dry_run=False)
