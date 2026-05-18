"""Hospital (Sykehus) action gating."""

from __future__ import annotations

import pytest

from mafibot.actions.hospital import HospitalAction
from mafibot.brain import _ordered_action_names
from mafibot.config import BotProfile
from mafibot.profile_options import needs_hospital_visit
from mafibot.state import GameState


def test_needs_hospital_visit():
    profile = BotProfile(hospital_health_threshold=80)
    assert needs_hospital_visit(profile, GameState(health_percent=70))
    assert not needs_hospital_visit(profile, GameState(health_percent=85))
    assert not needs_hospital_visit(profile, GameState(health_percent=100))


@pytest.mark.asyncio
async def test_hospital_can_run_when_low_health():
    profile = BotProfile(
        economy_order=["hospital", "crime"],
        hospital_health_threshold=80,
    )
    state = GameState(health_percent=50, hospital_ready=True)
    assert await HospitalAction().can_run(state, profile)


@pytest.mark.asyncio
async def test_hospital_skips_when_health_ok():
    profile = BotProfile(
        economy_order=["hospital", "crime"],
        hospital_health_threshold=80,
    )
    state = GameState(health_percent=90, hospital_ready=True)
    assert await HospitalAction().can_run(state, profile) is False


@pytest.mark.asyncio
async def test_hospital_not_enabled_without_action_in_order():
    profile = BotProfile(economy_order=["crime"], hospital_health_threshold=80)
    state = GameState(health_percent=40, hospital_ready=True)
    assert await HospitalAction().can_run(state, profile) is False


def test_brain_prioritizes_hospital_when_injured():
    profile = BotProfile(
        economy_order=["crime", "hospital", "business"],
        hospital_health_threshold=80,
    )
    state = GameState(health_percent=40)
    names = _ordered_action_names(profile, state)
    assert names[0] == "hospital"


@pytest.mark.asyncio
async def test_hospital_dry_run():
    profile = BotProfile(
        economy_order=["hospital"],
        hospital_health_threshold=75,
    )
    result = await HospitalAction().run(
        None,  # type: ignore[arg-type]
        GameState(health_percent=60),
        profile,
        None,  # type: ignore[arg-type]
        dry_run=True,
    )
    assert result.success
    assert "Sykehus" in result.message
