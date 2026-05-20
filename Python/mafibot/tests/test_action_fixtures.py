"""Table-driven can_run checks using discovered HTML fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from mafibot.actions.base import action_by_name
from mafibot.config import BotProfile, load_bot_profile
from mafibot.state import parse_from_html

DISCOVERED = Path(__file__).parent / "fixtures" / "discovered"
GAME_URL = "https://mafiaspillet.no/ms.php"


@pytest.mark.parametrize(
    "action_id,profile_name",
    [
        ("crime", "ranker"),
        ("travel", "ranker"),
        ("business", "okonom"),
        ("ship", "okonom"),
        ("bank", "okonom_full"),
        ("work", "okonom"),
        ("hospital", "ranker"),
        ("messages", "ranker"),
        ("family", "ranker"),
        ("minions", "minion_ranker"),
        ("missions", "early_ranker"),
        ("organized_crime", "ranker"),
        ("market", "early_ranker"),
        ("drugs", "ranker"),
        ("murder", "angriper"),
    ],
)
@pytest.mark.asyncio
async def test_action_can_run_against_fixture(action_id: str, profile_name: str):
    path = DISCOVERED / f"{action_id}.html"
    if not path.is_file():
        pytest.skip(f"missing fixture {path.name}")
    html = path.read_text(encoding="utf-8")
    state = await parse_from_html(html, page_url=GAME_URL)
    state.on_login_page = False
    state.in_jail = False
    profile = load_bot_profile(profile_name)
    action = action_by_name(action_id)
    assert action is not None
    result = await action.can_run(state, profile)
    assert isinstance(result, bool)
