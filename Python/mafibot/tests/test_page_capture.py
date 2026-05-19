"""Tests for iframe-aware parsing and discovery page merge."""

from __future__ import annotations

from pathlib import Path

import pytest

from mafibot.page_capture import html_to_plain_text
from mafibot.selectors import DEFAULT_SIDES, merge_discovered_pages
from mafibot.state import parse_from_html, parse_hotel_nightly_cost

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_parse_discovered_crime_html_includes_iframe_text():
    html = (FIXTURES / "discovered" / "crime.html").read_text(encoding="utf-8")
    text = html_to_plain_text(html)
    assert "Kriminalitet" in text or "krim" in text.lower()
    state = await parse_from_html(html, page_url="https://mafiaspillet.no/ms.php")
    assert state.in_game_shell


def test_parse_hotel_nightly_cost():
    assert parse_hotel_nightly_cost("Overnatt i rom for 12 500 kr") == 12500
    assert parse_hotel_nightly_cost("Velkommen") is None


def test_merge_discovered_pages_from_side_links():
    links = [
        {"side": "kriminalitet", "text": "Kriminalitet", "href": "?side=kriminalitet"},
        {"side": "folk", "text": "Undersåtter", "href": "?side=folk"},
    ]
    merged = merge_discovered_pages(links, None)
    assert merged["crime"] == "kriminalitet"
    assert merged["minions"] == "folk"


def test_merge_discovered_pages_from_tab_routes():
    tabs = [
        {
            "label": "Kriminalitet",
            "data_url": "game.php?p=krim",
            "route": "game.php?p=krim",
        },
        {
            "label": "Oppdrag",
            "data_url": "game.php?p=oppdrag2",
            "route": "game.php?p=oppdrag2",
        },
    ]
    merged = merge_discovered_pages([], tabs)
    assert merged["crime"] == "krim"
    assert merged["missions"] == "oppdrag2"
    assert merged["home"] == DEFAULT_SIDES["home"]
