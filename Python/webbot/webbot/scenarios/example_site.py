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


async def run(page: Page) -> None:
    await page.goto("https://example.com", wait_until="domcontentloaded")
    await reading_pause(1.0, 2.5)
    await idle_mouse_drift(page)

    heading = page.get_by_role("heading", name="Example Domain")
    await heading.wait_for(state="visible", timeout=15_000)
    await human_delay(0.5, 1.0)

    link = page.get_by_role("link", name="Learn more")
    await human_scroll(page, delta_y=120, steps=3)
    await human_delay(0.3, 0.8)
    await human_click(page, link)

    await page.wait_for_load_state("domcontentloaded")
    await reading_pause(1.0, 2.0)
