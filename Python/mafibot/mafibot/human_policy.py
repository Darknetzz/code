"""Human-like timing and interaction policy."""

from __future__ import annotations

import random
from dataclasses import dataclass

from playwright.async_api import Page

from webbot.human import human_delay, human_scroll, idle_mouse_drift, reading_pause


@dataclass
class HumanPolicy:
    jitter_min_sec: int = 15
    jitter_max_sec: int = 90
    long_pause_chance: float = 0.12
    scroll_before_click_chance: float = 0.35


def cooldown_jitter(policy: HumanPolicy) -> float:
    return random.uniform(policy.jitter_min_sec, policy.jitter_max_sec)


async def after_navigation(page: Page, policy: HumanPolicy | None = None) -> None:
    p = policy or HumanPolicy()
    await reading_pause(0.8, 2.4, distribution="triangular")
    if random.random() < 0.4:
        await idle_mouse_drift(page)
    await human_delay(
        0.2,
        0.9,
        distribution="triangular",
        long_pause_chance=p.long_pause_chance,
    )


async def between_actions(page: Page, policy: HumanPolicy | None = None) -> None:
    p = policy or HumanPolicy()
    await idle_mouse_drift(page)
    await human_delay(
        0.4,
        1.8,
        distribution="triangular",
        long_pause_chance=p.long_pause_chance,
        long_pause_min=2.0,
        long_pause_max=8.0,
    )


async def page_reading_pause(page: Page) -> None:
    try:
        text = await page.locator("body").inner_text()
        length = len(text)
    except Exception:
        length = 500
    if length < 400:
        await reading_pause(0.6, 1.8)
    elif length < 2000:
        await reading_pause(1.2, 3.5)
    else:
        await reading_pause(2.0, 6.0)


async def maybe_scroll_page(page: Page, policy: HumanPolicy | None = None) -> None:
    p = policy or HumanPolicy()
    if random.random() < p.scroll_before_click_chance:
        await human_scroll(page, delta_y=random.randint(120, 420))
