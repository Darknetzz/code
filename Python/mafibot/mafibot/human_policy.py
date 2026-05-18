"""Human-like timing — slow, variable gaps; never machine-gun clicks."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field

from playwright.async_api import Locator, Page

from webbot.human import human_click, human_delay, human_scroll, idle_mouse_drift, reading_pause

_last_click_at: float = 0.0


@dataclass
class HumanPolicy:
    jitter_min_sec: int = 30
    jitter_max_sec: int = 120
    long_pause_chance: float = 0.18
    scroll_before_click_chance: float = 0.4
    min_seconds_between_clicks: float = 2.8
    min_seconds_after_tab_change: float = 3.5
    pre_click_pause_min: float = 1.2
    pre_click_pause_max: float = 3.8
    think_before_action_chance: float = 0.25
    think_pause_min: float = 4.0
    think_pause_max: float = 12.0


def cooldown_jitter(policy: HumanPolicy) -> float:
    return random.uniform(policy.jitter_min_sec, policy.jitter_max_sec)


async def _enforce_click_gap(policy: HumanPolicy) -> None:
    global _last_click_at
    now = time.monotonic()
    gap = policy.min_seconds_between_clicks - (now - _last_click_at)
    if gap > 0:
        await asyncio.sleep(gap + random.uniform(0.15, 0.9))
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
    await reading_pause(p.min_seconds_after_tab_change, p.min_seconds_after_tab_change + 4.0)
    await after_navigation(page, p)


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
        await human_scroll(page, delta_y=random.randint(80, 320))
        await human_delay(0.4, 1.2)
