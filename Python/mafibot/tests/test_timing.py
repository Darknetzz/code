"""Timing helpers always return floats in range."""

from __future__ import annotations

import pytest

from mafibot.human_policy import (
    HumanPolicy,
    cycle_wait_after_action,
    cycle_wait_nothing_todo,
    hotel_transition_policy,
    idle_break_seconds,
    pause_before_book_hotel,
    random_wait_seconds,
)


def test_random_wait_is_float_in_range():
    for _ in range(50):
        v = random_wait_seconds(10.5, 20.25)
        assert isinstance(v, float)
        assert v != int(v) or 10.5 == 20.25  # usually non-integer
        assert 10.5 <= v <= 20.25


def test_cycle_waits_are_floats():
    p = HumanPolicy(jitter_min_sec=30.0, jitter_max_sec=40.0)
    a = cycle_wait_after_action(p)
    n = cycle_wait_nothing_todo(p)
    assert isinstance(a, float) and isinstance(n, float)
    assert n > a


@pytest.mark.asyncio
async def test_pause_before_book_hotel_respects_max():
    import time

    t0 = time.monotonic()
    slept = await pause_before_book_hotel(2.0)
    elapsed = time.monotonic() - t0
    assert slept <= 2.05
    assert elapsed <= 2.1


def test_idle_break_float_minutes():
    sec = idle_break_seconds(5.5, 12.25)
    assert isinstance(sec, float)
    assert 5.5 * 60 <= sec <= 12.25 * 60 + 0.01


def test_hotel_transition_policy_slower_than_old_fast_path():
    base = HumanPolicy(min_seconds_between_clicks=3.0, pre_click_pause_min=1.2)
    fast = hotel_transition_policy(base)
    assert fast.min_seconds_between_clicks >= 1.8
    assert fast.pre_click_pause_min >= 0.6
