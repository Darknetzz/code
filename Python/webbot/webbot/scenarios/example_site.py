"""Pilot scenario: human-like browsing on example.com (safe demo target)."""

from __future__ import annotations

from playwright.async_api import Page

from webbot.human import (
    human_click,
    human_delay,
    human_scroll,
    idle_mouse_drift,
    reading_pause,
)
from webbot.run_context import run_verified_step


async def run(page: Page) -> None:
    total = 5

    await run_verified_step(
        1,
        total,
        "goto https://example.com",
        lambda: page.goto("https://example.com", wait_until="domcontentloaded"),
    )
    await run_verified_step(2, total, "reading pause", lambda: reading_pause(1.0, 2.5))
    await run_verified_step(3, total, "idle mouse drift", lambda: idle_mouse_drift(page))

    heading = page.get_by_role("heading", name="Example Domain")

    async def wait_heading() -> None:
        await heading.wait_for(state="visible", timeout=15_000)
        await human_delay(0.5, 1.0)

    await run_verified_step(4, total, "wait for heading", wait_heading)

    link = page.get_by_role("link", name="Learn more")

    async def click_learn_more() -> None:
        await human_scroll(page, delta_y=120, steps=3)
        await human_delay(0.3, 0.8)
        await human_click(page, link)
        await page.wait_for_load_state("domcontentloaded")
        await reading_pause(1.0, 2.0)

    await run_verified_step(5, total, 'click link "Learn more"', click_learn_more)
