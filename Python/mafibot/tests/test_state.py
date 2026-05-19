"""Parser tests using HTML fixtures (no live site)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mafibot.brain import pick_next_action
from mafibot.config import BotProfile, load_bot_profile
from mafibot.hotel_stay import action_requires_leave_hotel
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
async def test_ms_hotel_in_hotel_crime_still_ready_for_scheduler():
    html = (FIXTURES / "ms_logged_in.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    assert state.in_hotel
    assert state.must_leave_hotel
    assert state.crime_ready  # cooldown ok; brain leaves hotel before crime
    assert state.business_income_ready
    assert state.ship_in_port


@pytest.mark.asyncio
async def test_pick_work_while_in_hotel_before_crime_if_both_ready():
    html = (FIXTURES / "ms_logged_in.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    profile = load_bot_profile("okonom")
    action, reason = await pick_next_action(state, profile)
    assert action is not None
    assert action.name == "work"


@pytest.mark.asyncio
async def test_crime_requires_leave():
    assert action_requires_leave_hotel("crime")
    assert not action_requires_leave_hotel("business")


@pytest.mark.asyncio
async def test_crime_cooldown():
    html = (FIXTURES / "crime_cooldown.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    assert state.logged_in
    assert not state.crime_ready
    assert len(state.active_cooldowns) == 1
    assert state.active_cooldowns[0].id == "crime"
    assert state.active_cooldowns[0].ready_at is not None


@pytest.mark.asyncio
async def test_active_cooldowns_empty_when_all_ready():
    html = (FIXTURES / "logged_in.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    assert state.active_cooldowns == []


@pytest.mark.asyncio
async def test_pick_hospital_when_health_below_threshold():
    html = (FIXTURES / "logged_in.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    profile = load_bot_profile("ranker")
    action, _reason = await pick_next_action(state, profile)
    assert action is not None
    assert action.name == "hospital"


@pytest.mark.asyncio
async def test_pick_crime_when_ready_and_health_ok():
    html = (FIXTURES / "logged_in.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    profile = load_bot_profile("ranker")
    profile.hospital_health_threshold = 70
    action, _reason = await pick_next_action(state, profile)
    assert action is not None
    assert action.name == "crime"


def test_extract_side():
    assert extract_side_from_href("?side=kriminalitet") == "kriminalitet"
    assert extract_side_from_href("/index.php?side=reise&x=1") == "reise"


def test_bot_profile_hotel_stay_defaults():
    p = load_bot_profile("ranker")
    assert p.stay_in_hotel is True
    assert p.book_hotel_after_every_action is True
    assert "leave_hotel" not in p.economy_order
