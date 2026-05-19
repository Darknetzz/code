"""Hotel economics and booking guards."""

from __future__ import annotations

import pytest

from mafibot.config import BotProfile
from mafibot.hotel_stay import hotel_booking_blocked_reason
from mafibot.state import GameState


def test_hotel_blocked_low_wallet():
    profile = BotProfile(name="t", hotel_min_wallet=1000, hotel_book_when_broke=False)
    state = GameState(money=500, page_text_sample="")
    assert hotel_booking_blocked_reason(state, profile) == "low_wallet"


def test_hotel_blocked_over_budget():
    profile = BotProfile(name="t", hotel_max_nightly_cost=5000)
    state = GameState(hotel_nightly_cost=8000, page_text_sample="")
    assert hotel_booking_blocked_reason(state, profile) == "over_budget"


def test_hotel_allowed_when_broke_flag_set():
    profile = BotProfile(name="t", hotel_min_wallet=1000, hotel_book_when_broke=True)
    state = GameState(money=100, page_text_sample="")
    assert hotel_booking_blocked_reason(state, profile) is None
