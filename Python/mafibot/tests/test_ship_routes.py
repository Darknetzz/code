"""Ship destination routing by current location."""

from __future__ import annotations

import pytest

from mafibot.actions.economy import ShipAction
from mafibot.config import BotProfile
from mafibot.ship_routes import (
    destinations_for_location,
    format_ship_routes_text,
    parse_ship_routes_text,
    pick_ship_destinations,
    ship_send_configured,
)
from mafibot.state import GameState


def test_parse_ship_routes_text():
    routes = parse_ship_routes_text(
        "Kabul: Oslo, New York\nOslo -> Detroit\n# comment\n"
    )
    assert routes == {
        "Kabul": ["Oslo", "New York"],
        "Oslo": ["Detroit"],
    }


def test_format_ship_routes_roundtrip():
    routes = {"Kabul": ["Oslo"], "Oslo": ["Detroit", "Rio"]}
    text = format_ship_routes_text(routes)
    assert parse_ship_routes_text(text) == routes


def test_destinations_for_location_route_match():
    profile = BotProfile(
        ship_routes={"Kabul": ["Oslo", "New York"]},
        ship_destinations=["Las Vegas"],
    )
    assert destinations_for_location(profile, "Kabul") == ["Oslo", "New York"]
    assert destinations_for_location(profile, "Oslo") == ["Las Vegas"]


def test_pick_ship_destinations_rotate():
    profile = BotProfile(
        ship_routes={"Kabul": ["Oslo", "Detroit"]},
        ship_rotate_destinations=True,
    )
    first = pick_ship_destinations(profile, "Kabul")
    second = pick_ship_destinations(profile, "Kabul")
    assert first == ["Oslo", "Detroit"]
    assert second == ["Detroit", "Oslo"]


def test_ship_send_configured():
    assert not ship_send_configured(BotProfile())
    assert ship_send_configured(BotProfile(ship_destinations=["Oslo"]))
    assert ship_send_configured(BotProfile(ship_routes={"Kabul": ["Oslo"]}))


@pytest.mark.asyncio
async def test_ship_dry_run_with_route():
    profile = BotProfile(ship_routes={"Kabul": ["Oslo"]})
    state = GameState(location="Kabul", ship_in_port=True)
    result = await ShipAction().run(
        None,  # type: ignore[arg-type]
        state,
        profile,
        None,  # type: ignore[arg-type]
        dry_run=True,
    )
    assert result.success
    assert "Oslo" in result.message
