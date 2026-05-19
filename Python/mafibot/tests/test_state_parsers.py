"""Extended GameState parser tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from mafibot.config import load_bot_profile
from mafibot.scheduler import ordered_action_names
from mafibot.state import parse_from_html
from mafibot.state_parsers import parse_extended_state, parse_happy_hour_buffs

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_extended_state_parsing():
    html = (FIXTURES / "extended_state.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    assert state.attack == 25
    assert state.protection == 30
    assert state.mission_number == 3
    assert state.mission_progress_current == 2
    assert state.mission_progress_total == 10
    assert state.mission_requirement_hint == "crime"
    assert state.happy_hour_active
    assert "double_crime_rank" in state.happy_hour_buffs
    assert state.family_war_active
    assert state.crime_enkel_ready
    assert not state.crime_tung_ready
    assert len(state.report_entries) >= 1
    assert state.report_entries[0].null_delay


@pytest.mark.asyncio
async def test_restricted_state():
    html = (FIXTURES / "restricted_state.html").read_text(encoding="utf-8")
    state = await parse_from_html(html)
    assert state.kidnapped
    assert state.feriemodus
    assert state.startbeskyttelse
    assert state.gameplay_restricted()


def test_happy_hour_parser():
    text = "Happy Hour: halv pris skudd og dobbelt rankpoeng krim"
    buffs = parse_happy_hour_buffs(text)
    assert "half_bullet_price" in buffs
    assert "double_crime_rank" in buffs


@pytest.mark.asyncio
async def test_scheduler_boosts_missions_first():
    html = (FIXTURES / "extended_state.html").read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    profile = load_bot_profile("early_ranker")
    order = ordered_action_names(profile, state)
    assert order.index("crime") < order.index("business")
