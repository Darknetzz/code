"""Human-like timing — slow, variable gaps; never machine-gun clicks."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass

from playwright.async_api import Locator, Page

from webbot.human import (
    DelayDistribution,
    human_click,
    human_delay,
    human_scroll,
    idle_mouse_drift,
    reading_pause,
)

log = logging.getLogger("mafibot.timing")

_last_click_at: float = 0.0


def random_wait_seconds(
    min_sec: float,
    max_sec: float,
    *,
    distribution: DelayDistribution = "uniform",
) -> float:
    """Sample a wait duration in seconds (always a float, never rounded to int)."""
    if max_sec <= min_sec:
        return float(min_sec)
    if distribution == "triangular":
        mode = min_sec + (max_sec - min_sec) * random.uniform(0.25, 0.45)
        return random.triangular(min_sec, max_sec, mode)
    if distribution == "log_normal":
        import math

        mu = math.log(min_sec + (max_sec - min_sec) * 0.25)
        return float(min(max_sec, max(min_sec, random.lognormvariate(mu, 0.45))))
    return random.uniform(min_sec, max_sec)


async def sleep_wait(
    min_sec: float,
    max_sec: float,
    *,
    distribution: DelayDistribution = "uniform",
    label: str | None = None,
) -> float:
    """Sleep for a random float duration; return seconds slept."""
    seconds = random_wait_seconds(min_sec, max_sec, distribution=distribution)
    if label:
        log.debug("sleep %s: %.2fs", label, seconds)
    await asyncio.sleep(seconds)
    return seconds


@dataclass
class HumanPolicy:
    jitter_min_sec: float = 30.0
    jitter_max_sec: float = 120.0
    jitter_distribution: DelayDistribution = "triangular"
    long_pause_chance: float = 0.18
    scroll_before_click_chance: float = 0.4
    min_seconds_between_clicks: float = 2.8
    min_seconds_after_tab_change: float = 3.5
    pre_click_pause_min: float = 1.2
    pre_click_pause_max: float = 3.8
    think_before_action_chance: float = 0.25
    think_pause_min: float = 4.0
    think_pause_max: float = 12.0
    # Extra float waits after each brain cycle (added to jitter)
    post_action_wait_min_sec: float = 8.0
    post_action_wait_max_sec: float = 25.0
    nothing_todo_wait_min_sec: float = 45.0
    nothing_todo_wait_max_sec: float = 180.0


def cooldown_jitter(policy: HumanPolicy) -> float:
    return random_wait_seconds(
        policy.jitter_min_sec,
        policy.jitter_max_sec,
        distribution=policy.jitter_distribution,
    )


def cycle_wait_after_action(policy: HumanPolicy) -> float:
    """Total seconds to wait before the next brain cycle (float sum)."""
    return cooldown_jitter(policy) + random_wait_seconds(
        policy.post_action_wait_min_sec,
        policy.post_action_wait_max_sec,
        distribution="triangular",
    )


def cycle_wait_nothing_todo(policy: HumanPolicy) -> float:
    return cooldown_jitter(policy) + random_wait_seconds(
        policy.nothing_todo_wait_min_sec,
        policy.nothing_todo_wait_max_sec,
        distribution="triangular",
    )


async def _enforce_click_gap(policy: HumanPolicy) -> None:
    global _last_click_at
    now = time.monotonic()
    gap = policy.min_seconds_between_clicks - (now - _last_click_at)
    if gap > 0:
        extra = random_wait_seconds(0.15, 0.9)
        await asyncio.sleep(gap + extra)
    _last_click_at = time.monotonic()


async def maybe_think_pause(policy: HumanPolicy) -> None:
    if random.random() < policy.think_before_action_chance:
        await reading_pause(
            policy.think_pause_min,
            policy.think_pause_max,
            distribution="triangular",
        )


async def human_click_paced(
    page: Page,
    locator: Locator,
    policy: HumanPolicy | None = None,
) -> None:
    """Bezier click with mandatory minimum gap since last click."""
    p = policy or HumanPolicy()
    await _enforce_click_gap(p)
    await reading_pause(p.pre_click_pause_min, p.pre_click_pause_max, distribution="triangular")
    if random.random() < 0.35:
        await idle_mouse_drift(page)
    await human_click(page, locator)
    await human_delay(0.5, 1.6, distribution="triangular", long_pause_chance=0.08)


async def after_navigation(page: Page, policy: HumanPolicy | None = None) -> None:
    p = policy or HumanPolicy()
    await reading_pause(2.0, 5.0, distribution="triangular")
    if random.random() < 0.55:
        await idle_mouse_drift(page)
    await human_delay(
        0.8,
        2.2,
        distribution="triangular",
        long_pause_chance=p.long_pause_chance,
        long_pause_min=3.0,
        long_pause_max=10.0,
    )


async def after_tab_change(page: Page, policy: HumanPolicy | None = None) -> None:
    p = policy or HumanPolicy()
    tab_span = random_wait_seconds(0.0, 4.0, distribution="uniform")
    await reading_pause(
        p.min_seconds_after_tab_change,
        p.min_seconds_after_tab_change + tab_span,
        distribution="triangular",
    )
    await after_navigation(page, p)


async def pause_before_book_hotel(max_seconds: float = 2.0) -> float:
    """Short gap after gameplay action, before booking hotel (capped)."""
    if max_seconds <= 0:
        return 0.0
    seconds = random_wait_seconds(0.05, max_seconds, distribution="uniform")
    await asyncio.sleep(seconds)
    return seconds


def hotel_transition_policy(base: HumanPolicy) -> HumanPolicy:
    """Faster clicks for leave/book steps; still human-like."""
    return HumanPolicy(
        jitter_min_sec=base.jitter_min_sec,
        jitter_max_sec=base.jitter_max_sec,
        min_seconds_between_clicks=min(1.2, base.min_seconds_between_clicks),
        min_seconds_after_tab_change=min(1.5, base.min_seconds_after_tab_change),
        pre_click_pause_min=0.4,
        pre_click_pause_max=1.2,
        think_before_action_chance=0.05,
        long_pause_chance=0.05,
    )


async def between_actions(page: Page, policy: HumanPolicy | None = None) -> None:
    p = policy or HumanPolicy()
    await idle_mouse_drift(page)
    await human_delay(
        2.0,
        5.5,
        distribution="triangular",
        long_pause_chance=p.long_pause_chance,
        long_pause_min=4.0,
        long_pause_max=14.0,
    )


async def page_reading_pause(page: Page) -> None:
    try:
        text = await page.locator("body").inner_text()
        length = len(text)
    except Exception:
        length = 500
    if length < 400:
        await reading_pause(1.5, 3.5)
    elif length < 2000:
        await reading_pause(2.5, 6.0)
    else:
        await reading_pause(4.0, 10.0)


async def maybe_scroll_page(page: Page, policy: HumanPolicy | None = None) -> None:
    p = policy or HumanPolicy()
    if random.random() < p.scroll_before_click_chance:
        delta = random_wait_seconds(80.0, 320.0)
        await human_scroll(page, delta_y=int(delta))
        await human_delay(0.4, 1.2)


def idle_break_seconds(idle_min_minutes: float, idle_max_minutes: float) -> float:
    """AFK break length in seconds (float minutes → float seconds)."""
    minutes = random_wait_seconds(idle_min_minutes, idle_max_minutes, distribution="triangular")
    return minutes * 60.0
