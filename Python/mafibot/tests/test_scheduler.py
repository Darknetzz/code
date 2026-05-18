from datetime import datetime, timedelta

import pytest

from mafibot.actions.base import all_actions
from mafibot.config import BotProfile
from mafibot.scheduler import pick_soonest_ready, pick_runnable_actions
from mafibot.state import GameState, ActionCooldown


@pytest.mark.asyncio
async def test_pick_runnable_respects_can_run():
    profile = BotProfile(crime_actions=["enkel"])
    state = GameState(crime_ready=False, in_jail=False)
    crime = next(a for a in all_actions() if a.name == "crime")
    runnable = await pick_runnable_actions(state, profile, [crime])
    assert runnable == []


def test_soonest_ready_tiebreaks_by_order():
    profile = BotProfile()
    state = GameState(
        crime_ready=True,
        ship_ready=True,
        work_ready=True,
    )
    crime = next(a for a in all_actions() if a.name == "crime")
    ship = next(a for a in all_actions() if a.name == "ship")
    runnable = [(crime, ""), (ship, "")]
    picked = pick_soonest_ready(runnable, state, ["crime", "ship"])
    assert picked is not None
    assert picked[0].name == "crime"


def test_soonest_ready_prefers_earlier_cooldown_end():
    profile = BotProfile()
    soon = datetime.now() + timedelta(minutes=1)
    later = datetime.now() + timedelta(minutes=10)
    state = GameState(
        crime_ready=False,
        ship_ready=True,
        active_cooldowns=[
            ActionCooldown(id="crime", label="Crime", ready_at=soon),
        ],
    )
    crime = next(a for a in all_actions() if a.name == "crime")
    ship = next(a for a in all_actions() if a.name == "ship")
    state.crime_ready = False
    state.ship_ready = True
    runnable = [(ship, "")]
    picked = pick_soonest_ready(runnable, state, ["crime", "ship"])
    assert picked and picked[0].name == "ship"
