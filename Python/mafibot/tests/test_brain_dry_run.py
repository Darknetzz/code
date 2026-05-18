"""Brain dry-run decisions."""

from __future__ import annotations

from pathlib import Path

import pytest

from mafibot.brain import pick_next_action
from mafibot.config import load_bot_profile
from mafibot.state import parse_from_html

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_dry_run_picks_economy_order():
    html = (FIXTURES / "crime_cooldown.html").read_text(encoding="utf-8")
    state = await parse_from_html(html)
    profile = load_bot_profile("okonom")
    action, _ = await pick_next_action(state, profile, dry_run=True)
    assert action is not None
    assert action.name in profile.economy_order or action.name in ("travel", "business", "bank")
