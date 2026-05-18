"""Bank balance planning and murder target gating."""

from __future__ import annotations

import pytest

from mafibot.action_targets import murder_target_names, pick_murder_target
from mafibot.actions.combat import MurderAction
from mafibot.actions.economy import BankAction
from mafibot.config import BotProfile
from mafibot.page_actions import bank_adjustment
from mafibot.state import GameState, parse_bank_balance_from_text


def test_parse_bank_balance():
    text = "Penger: 50 000 kr\nBank: 1 200 000 kr"
    assert parse_bank_balance_from_text(text) == 1_200_000


def test_bank_adjustment_withdraw():
    plan = bank_adjustment(30_000, 500_000, target_cash=100_000, tolerance=10_000)
    assert plan == ("withdraw", 70_000)


def test_bank_adjustment_deposit():
    plan = bank_adjustment(200_000, None, target_cash=100_000, tolerance=10_000)
    assert plan == ("deposit", 100_000)


def test_bank_adjustment_in_range():
    assert bank_adjustment(105_000, 50_000, target_cash=100_000, tolerance=10_000) is None


@pytest.mark.asyncio
async def test_bank_auto_skips_when_balanced():
    profile = BotProfile(
        economy_order=["bank"],
        bank_auto_balance=True,
        bank_keep_cash_on_hand=100_000,
        bank_balance_tolerance=10_000,
    )
    state = GameState(money=100_000, bank_balance=50_000)
    action = BankAction()
    assert await action.can_run(state, profile) is False


@pytest.mark.asyncio
async def test_murder_requires_targets():
    profile = BotProfile(combat_enabled=True, aggression=0.9, murder_targets=[])
    state = GameState(murder_ready=True, health_percent=90)
    assert murder_target_names(profile) == []
    assert await MurderAction().can_run(state, profile) is False


@pytest.mark.asyncio
async def test_messages_only_when_unread():
    profile = BotProfile(
        social_enabled=True,
        messages_only_when_unread=True,
        messages_interval_minutes=60,
    )
    state = GameState(unread_messages=0)
    from mafibot.actions.social import MessagesAction

    assert await MessagesAction().can_run(state, profile) is False
    state.unread_messages = 2
    assert await MessagesAction().can_run(state, profile) is True


def test_pick_murder_target_rotate():
    profile = BotProfile(
        murder_targets=["alice", "bob"],
        murder_rotate_targets=True,
    )
    first = pick_murder_target(profile)
    second = pick_murder_target(profile)
    assert {first, second} == {"alice", "bob"}
    assert first != second
