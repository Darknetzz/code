"""Crime profile options and gating."""

from __future__ import annotations

import pytest

from mafibot.actions.crime import CrimeAction
from mafibot.config import BotProfile
from mafibot.profile_options import (
    crime_entry_labels,
    crime_perform_variant_labels,
    crime_steal_item_labels,
    crime_submit_labels,
)
from mafibot.state import GameState


def test_crime_entry_labels_by_kind():
    perform = BotProfile(crime_kind="perform")
    steal = BotProfile(crime_kind="steal")
    assert crime_entry_labels(perform) == ("utfør", "begå")
    assert crime_entry_labels(steal) == ("stjel", "tyveri")


def test_crime_perform_variant_labels():
    assert crime_perform_variant_labels(BotProfile(crime_perform_type="lett")) == (
        "lett kriminalitet",
        "lett",
        "enkel kriminalitet",
        "enkel",
    )
    assert crime_perform_variant_labels(BotProfile(crime_perform_type="tung")) == (
        "tung kriminalitet",
        "tung",
    )
    assert crime_perform_variant_labels(BotProfile(crime_perform_type="any")) == ()


def test_crime_steal_item_labels():
    assert crime_steal_item_labels(BotProfile(crime_steal_what="våpen")) == ("våpen",)


def test_crime_submit_labels_override():
    profile = BotProfile(crime_button_labels=["go", "run"])
    assert crime_submit_labels(profile) == ("go", "run")


@pytest.mark.asyncio
async def test_crime_steal_specific_requires_username():
    profile = BotProfile(
        crime_kind="steal",
        crime_steal_target_mode="specific",
        crime_steal_username="",
    )
    state = GameState(crime_ready=True, health_percent=90)
    assert await CrimeAction().can_run(state, profile) is False

    profile.crime_steal_username = "rival"
    assert await CrimeAction().can_run(state, profile) is True


@pytest.mark.asyncio
async def test_crime_dry_run_steal_message():
    profile = BotProfile(
        crime_kind="steal",
        crime_steal_what="bil",
        crime_steal_target_mode="random",
    )
    result = await CrimeAction().run(
        None,  # type: ignore[arg-type]
        GameState(),
        profile,
        None,  # type: ignore[arg-type]
        dry_run=True,
    )
    assert result.success
    assert "steal=bil" in result.message
