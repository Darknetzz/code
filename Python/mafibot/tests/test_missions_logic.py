"""Mission delegation logic tests."""

from __future__ import annotations

import pytest

from mafibot.config import BotProfile
from mafibot.missions_logic import preferred_actions_for_mission
from mafibot.state import GameState


@pytest.mark.parametrize(
    "hint,expected",
    [
        ("crime", ["crime"]),
        ("buy_weapon", ["market", "crime"]),
        ("minions_train", ["minions"]),
    ],
)
def test_preferred_actions_from_hint(hint: str, expected: list[str]):
    profile = BotProfile(missions_enabled=True, missions_mode="auto_progress")
    state = GameState(mission_requirement_hint=hint, missions_in_progress=True)
    assert preferred_actions_for_mission(state, profile) == expected
