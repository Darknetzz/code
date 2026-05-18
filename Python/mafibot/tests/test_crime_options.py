"""Crime profile options and gating."""

from __future__ import annotations

import pytest

from mafibot.actions.crime import CrimeAction
from mafibot.config import BotProfile
from mafibot.crime_catalog import (
    crime_actions_enabled,
    pick_crime_section,
    pick_option_ids,
)
from mafibot.profile_options import crime_needs_steal_username, crime_submit_labels
from mafibot.state import GameState


def test_legacy_migrate_steal():
    profile = BotProfile(crime_kind="steal", crime_steal_what="penger")
    assert crime_actions_enabled(profile) == ["stjel"]


def test_legacy_migrate_perform_both():
    profile = BotProfile(crime_kind="perform", crime_perform_type="any")
    assert set(crime_actions_enabled(profile)) == {"enkel", "tung"}


def test_crime_submit_labels_override():
    profile = BotProfile(crime_button_labels=["go", "run"])
    assert crime_submit_labels(profile) == ("go", "run")


def test_rotate_crime_sections():
    profile = BotProfile(
        crime_actions=["enkel", "tung", "stjel"],
        crime_rotate_actions=True,
    )
    first = pick_crime_section(profile)
    second = pick_crime_section(profile)
    third = pick_crime_section(profile)
    assert {first, second, third} == {"enkel", "tung", "stjel"}


def test_pick_option_ids_empty_means_all():
    profile = BotProfile(crime_actions=["enkel"], crime_enkel_choices=[])
    ids = pick_option_ids(profile, "enkel")
    assert ids == ["automat", "kiosk", "gate", "butikk"]


@pytest.mark.asyncio
async def test_crime_steal_specific_requires_username():
    profile = BotProfile(
        crime_actions=["stjel"],
        crime_steal_target_mode="specific",
        crime_steal_username="",
    )
    state = GameState(crime_ready=True, health_percent=90)
    assert crime_needs_steal_username(profile)
    assert await CrimeAction().can_run(state, profile) is False

    profile.crime_steal_username = "rival"
    assert await CrimeAction().can_run(state, profile) is True


@pytest.mark.asyncio
async def test_crime_dry_run_lists_actions():
    profile = BotProfile(
        crime_actions=["enkel", "stjel"],
        crime_steal_items=["penger"],
        crime_rotate_actions=True,
    )
    result = await CrimeAction().run(
        None,  # type: ignore[arg-type]
        GameState(health_percent=90),
        profile,
        None,  # type: ignore[arg-type]
        dry_run=True,
    )
    assert result.success
    assert "actions=enkel,stjel" in result.message
