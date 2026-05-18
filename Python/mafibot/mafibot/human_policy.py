"""Human-like timing — slow, variable gaps; never machine-gun clicks."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, replace

from playwright.async_api import Locator, Page

from webbot.human import (
    DelayDistribution,
    human_delay,
    human_scroll,
    idle_mouse_drift,
    move_mouse_human,
    reading_pause,
)

log = logging.getLogger("mafibot.timing")

_last_click_at: float = 0.0
_last_mouse: tuple[float, float] | None = None


def reset_mouse_position() -> None:
    global _last_mouse
    _last_mouse = None


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


async def _idle_micro_activity(page: Page, policy: HumanPolicy) -> None:
    roll = random.random()
    if roll < 0.40:
        await idle_mouse_drift(page)
    elif roll < 0.65:
        delta = int(random_wait_seconds(40.0, 160.0))
        await human_scroll(page, delta_y=delta)
        await human_delay(0.4, 1.2)
    elif roll < 0.80:
        await reading_pause(1.0, 3.0, distribution="triangular")


async def sleep_with_idle_activity(
    page: Page,
    total_seconds: float,
    policy: HumanPolicy | None = None,
    *,
    cancel: asyncio.Event | None = None,
) -> bool:
    """
    Sleep for roughly total_seconds with occasional drift/scroll between chunks.
    Returns False if cancel is set before the wait completes.
    """
    if total_seconds <= 0:
        return cancel is None or not cancel.is_set()

    p = policy or HumanPolicy()
    target = total_seconds
    tolerance = max(0.5, target * 0.05)
    elapsed = 0.0

    while elapsed < target - tolerance:
        if cancel and cancel.is_set():
            return False
        remaining = target - elapsed
        chunk_hi = min(25.0, max(5.0, remaining))
        chunk = random_wait_seconds(5.0, chunk_hi)
        chunk = min(chunk, remaining)
        await asyncio.sleep(chunk)
        elapsed += chunk
        if cancel and cancel.is_set():
            return False
        if elapsed < target - tolerance:
            await _idle_micro_activity(page, p)

    pad = max(0.0, target - elapsed)
    if pad > 0:
        if cancel:
            try:
                await asyncio.wait_for(cancel.wait(), timeout=pad)
                return False
            except asyncio.TimeoutError:
                pass
        else:
            await asyncio.sleep(pad)
    return cancel is None or not cancel.is_set()


async def wait_with_idle_activity(
    page: Page,
    total_seconds: float,
    policy: HumanPolicy,
    cancel: asyncio.Event,
) -> bool:
    """Wait up to total_seconds with micro-activity; False when cancel fires."""
    return await sleep_with_idle_activity(page, total_seconds, policy, cancel=cancel)


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


async def _target_point_from_locator(locator: Locator) -> tuple[float, float]:
    box = await locator.bounding_box()
    if not box:
        raise RuntimeError("Element has no bounding box — is it visible?")
    x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
    y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
    return x, y


def _drift_chance(policy: HumanPolicy) -> float:
    return min(0.55, 0.25 + policy.long_pause_chance)


async def _human_move_and_click(
    page: Page,
    locator: Locator,
    *,
    allow_overshoot: bool = True,
) -> None:
    """Bezier move from last position, optional overshoot, hover settle, click."""
    global _last_mouse

    await locator.scroll_into_view_if_needed()
    await human_delay(0.1, 0.4)

    x, y = await _target_point_from_locator(locator)
    start = _last_mouse

    if allow_overshoot and random.random() < 0.03:
        box = await locator.bounding_box()
        if box and box["width"] * box["height"] > 8000:
            ox = random.uniform(-15.0, 15.0)
            oy = random.uniform(-15.0, 15.0)
            await move_mouse_human(page, x + ox, y + oy, start=start)
            await asyncio.sleep(random.uniform(0.06, 0.14))
            start = (x + ox, y + oy)

    await move_mouse_human(page, x, y, start=start)
    _last_mouse = (x, y)
    await asyncio.sleep(random.uniform(0.08, 0.22))
    await page.mouse.click(x, y)
    await human_delay(0.2, 0.6)


async def human_click_paced(
    page: Page,
    locator: Locator,
    policy: HumanPolicy | None = None,
    *,
    allow_overshoot: bool = True,
) -> None:
    """Bezier click with mandatory minimum gap since last click."""
    p = policy or HumanPolicy()
    await maybe_think_pause(p)
    await maybe_scroll_page(page, p)
    await _enforce_click_gap(p)
    await reading_pause(p.pre_click_pause_min, p.pre_click_pause_max, distribution="triangular")
    if random.random() < _drift_chance(p):
        await idle_mouse_drift(page)
    await _human_move_and_click(page, locator, allow_overshoot=allow_overshoot)
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
    """Faster clicks for leave/book steps; occasionally use full gameplay pacing."""
    if random.random() < 0.20:
        return base
    return HumanPolicy(
        jitter_min_sec=base.jitter_min_sec,
        jitter_max_sec=base.jitter_max_sec,
        jitter_distribution=base.jitter_distribution,
        long_pause_chance=0.08,
        scroll_before_click_chance=base.scroll_before_click_chance * 0.5,
        min_seconds_between_clicks=max(1.8, base.min_seconds_between_clicks * 0.65),
        min_seconds_after_tab_change=max(1.8, base.min_seconds_after_tab_change * 0.55),
        pre_click_pause_min=0.6,
        pre_click_pause_max=1.6,
        think_before_action_chance=0.08,
        think_pause_min=base.think_pause_min,
        think_pause_max=base.think_pause_max,
        post_action_wait_min_sec=base.post_action_wait_min_sec,
        post_action_wait_max_sec=base.post_action_wait_max_sec,
        nothing_todo_wait_min_sec=base.nothing_todo_wait_min_sec,
        nothing_todo_wait_max_sec=base.nothing_todo_wait_max_sec,
    )


def policy_after_afk_warmup(base: HumanPolicy) -> HumanPolicy:
    """Slightly longer post-action waits for a few cycles after an AFK break."""
    return replace(
        base,
        post_action_wait_min_sec=base.post_action_wait_min_sec * 1.15,
        post_action_wait_max_sec=base.post_action_wait_max_sec * 1.25,
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
