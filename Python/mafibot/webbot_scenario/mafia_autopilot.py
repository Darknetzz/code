"""
Webbot Python scenario: Mafiaspillet autopilot.

Install: python mafibot.py install-webbot-scenario
Run: cd Python/webbot && python webbot.py run mafia_autopilot
Requires: mafibot login first (shared profile recommended).
Env: MAFIBOT_PROFILE, MAFIBOT_MAX_MINUTES, MAFIBOT_DRY_RUN=1
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

from mafibot.auth import ensure_session, is_logged_in
from mafibot.brain import is_stop_requested, request_stop, run_session
from mafibot.config import GAME_URL, load_bot_profile
from mafibot.navigation import ensure_game_shell

DESCRIPTION = "Mafiaspillet autopilot (requires mafibot login)"
STEP_LABELS = ("autopilot session",)


def _env_bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


async def run(page: Page) -> None:
    profile_name = os.getenv("MAFIBOT_PROFILE", "ranker")
    profile = load_bot_profile(profile_name)
    max_minutes = int(os.getenv("MAFIBOT_MAX_MINUTES", str(profile.max_session_minutes)))
    dry_run = _env_bool("MAFIBOT_DRY_RUN")

    if "about:blank" in page.url or not page.url.startswith("http"):
        await page.goto(GAME_URL, wait_until="domcontentloaded")
    if not await is_logged_in(page):
        await ensure_session(page, manual=True)
    await ensure_game_shell(page)

    try:
        await run_session(page, profile, max_minutes=max_minutes, dry_run=dry_run)
    finally:
        if is_stop_requested():
            request_stop()
