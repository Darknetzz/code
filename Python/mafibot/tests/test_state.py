"""Parser tests using HTML fixtures (no live site)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mafibot.brain import pick_next_action
from mafibot.config import BotProfile, load_bot_profile
from mafibot.config import in_play_window
from mafibot.navigation import extract_side_from_href
from mafibot.state import parse_from_html

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_login_page_not_logged_in():
    html = (FIXTURES / "login_page.html").read_text(encoding="utf-8")
    state = await parse_from_html(html)
    assert state.on_login_page
    assert not state.logged_in
    assert state.needs_stop


@pytest.mark.asyncio
async def test_logged_in_parses_stats():
    html = (FIXTURES / "logged_in.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/?side=forsiden")
    assert state.logged_in
    assert state.money == 1250000
    assert state.rank_points == 42100
    assert state.health_percent == 78
    assert "Oslo" in (state.location or "")
    assert state.unread_messages == 3
    assert state.crime_ready


@pytest.mark.asyncio
async def test_crime_cooldown():
    html = (FIXTURES / "crime_cooldown.html").read_text(encoding="utf-8")
    state = await parse_from_html(html)
    assert state.logged_in
    assert not state.crime_ready


@pytest.mark.asyncio
async def test_pick_crime_when_ready():
    html = (FIXTURES / "logged_in.html").read_text(encoding="utf-8")
    state = await parse_from_html(html)
    profile = load_bot_profile("ranker")
    action, reason = await pick_next_action(state, profile)
    assert action is not None
    assert action.name == "crime"
    assert "crime" in reason


def test_extract_side():
    assert extract_side_from_href("?side=kriminalitet") == "kriminalitet"
    assert extract_side_from_href("/index.php?side=reise&x=1") == "reise"


def test_bot_profile_defaults():
    p = BotProfile()
    assert p.name == "ranker"
    assert in_play_window(p) in (True, False)
