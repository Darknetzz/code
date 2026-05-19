"""Tests for new gameplay actions."""

from __future__ import annotations

import pytest

from mafibot.actions.minions import MinionsAction
from mafibot.actions.missions import MissionsAction
from mafibot.actions.organized_crime import OrganizedCrimeAction
from mafibot.actions.market import MarketAction
from mafibot.config import BotProfile
from mafibot.state import GameState


@pytest.mark.asyncio
async def test_minions_disabled_by_default():
    action = MinionsAction()
    profile = BotProfile(name="test")
    state = GameState(minions_ready=True)
    assert not await action.can_run(state, profile)


@pytest.mark.asyncio
async def test_minions_runs_when_enabled():
    action = MinionsAction()
    profile = BotProfile(name="test", minions_enabled=True)
    state = GameState(minions_ready=True)
    assert await action.can_run(state, profile)


@pytest.mark.asyncio
async def test_missions_skip_when_in_progress():
    action = MissionsAction()
    profile = BotProfile(name="test", missions_enabled=True)
    state = GameState(missions_in_progress=True, missions_ready=True)
    assert not await action.can_run(state, profile)


@pytest.mark.asyncio
async def test_organized_crime_requires_enable():
    action = OrganizedCrimeAction()
    profile = BotProfile(name="test", organized_crime_enabled=False)
    state = GameState(organized_crime_ready=True, health_percent=90)
    assert not await action.can_run(state, profile)


@pytest.mark.asyncio
async def test_market_disabled_when_mode_none():
    action = MarketAction()
    profile = BotProfile(name="test", market_enabled=True, market_mode="none")
    state = GameState(market_ready=True)
    assert not await action.can_run(state, profile)
