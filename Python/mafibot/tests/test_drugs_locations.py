"""Drug city rules and travel dependency."""

from __future__ import annotations

import pytest

from mafibot.actions.economy import DrugsAction
from mafibot.actions.travel import TravelAction
from mafibot.config import BotProfile
from mafibot.drugs_locations import (
    drugs_destination_needed,
    location_allows_drugs,
)
from mafibot.state import GameState


def test_buy_only_in_kabul():
    profile = BotProfile(economy_order=["drugs"], drugs_prefer="buy")
    assert location_allows_drugs(profile, "Kabul")
    assert not location_allows_drugs(profile, "Oslo")
    assert drugs_destination_needed(profile, "Oslo") == "Kabul"


def test_sell_only_in_sell_cities():
    profile = BotProfile(economy_order=["drugs"], drugs_prefer="sell")
    assert location_allows_drugs(profile, "New York")
    assert not location_allows_drugs(profile, "Kabul")
    assert drugs_destination_needed(profile, "Kabul") is not None


@pytest.mark.asyncio
async def test_drugs_can_run_requires_city():
    profile = BotProfile(economy_order=["drugs"], drugs_prefer="buy")
    action = DrugsAction()
    assert await action.can_run(GameState(location="Kabul"), profile)
    assert not await action.can_run(GameState(location="Oslo"), profile)


@pytest.mark.asyncio
async def test_travel_runs_when_drugs_needs_city():
    profile = BotProfile(economy_order=["drugs", "travel"], drugs_prefer="buy")
    state = GameState(location="Oslo", travel_ready=True)
    assert drugs_destination_needed(profile, state.location) == "Kabul"
    assert await TravelAction().can_run(state, profile)
