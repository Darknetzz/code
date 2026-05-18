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


@pytest.mark.asyncio
async def test_logged_in_parses_stats():
    html = (FIXTURES / "logged_in.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    assert state.logged_in
    assert state.in_game_shell
    assert state.money == 1250000
    assert state.rank_points == 42100
    assert state.health_percent == 78
    assert state.unread_messages == 3
    assert state.crime_ready


@pytest.mark.asyncio
async def test_ms_hotel_blocks_crime():
    html = (FIXTURES / "ms_logged_in.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    assert state.in_hotel
    assert state.must_leave_hotel
    assert not state.crime_ready
    assert state.business_income_ready
    assert state.ship_in_port


@pytest.mark.asyncio
async def test_pick_leave_hotel_first():
    html = (FIXTURES / "ms_logged_in.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    profile = load_bot_profile("ranker")
    action, reason = await pick_next_action(state, profile)
    assert action is not None
    assert action.name == "leave_hotel"
    assert "hotel" in reason.lower()


@pytest.mark.asyncio
async def test_crime_cooldown():
    html = (FIXTURES / "crime_cooldown.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    assert state.logged_in
    assert not state.crime_ready


@pytest.mark.asyncio
async def test_pick_crime_when_ready():
    html = (FIXTURES / "logged_in.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    profile = load_bot_profile("ranker")
    action, reason = await pick_next_action(state, profile)
    assert action is not None
    assert action.name == "crime"


def test_extract_side():
    assert extract_side_from_href("?side=kriminalitet") == "kriminalitet"
    assert extract_side_from_href("/index.php?side=reise&x=1") == "reise"


def test_bot_profile_human_pacing_defaults():
    p = BotProfile()
    assert p.min_seconds_between_clicks >= 2.5
    assert p.cooldown_jitter_min_sec >= 30
