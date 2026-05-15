"""
Editable Python scenario (GUI: open this flow and edit in the Python panel).

Requires: async def run(page) using run_verified_step for live step progress.
Optional: DESCRIPTION, STEP_LABELS (for previews and the dashboard).
"""

from __future__ import annotations

from playwright.async_api import Page

from webbot.human import human_click, idle_mouse_drift, reading_pause
from webbot.locators import resolve_locator
from webbot.run_context import run_verified_step

DESCRIPTION = "Demo Python flow on example.com (edit freely in the dashboard)"
STEP_LABELS = (
    "goto example.com",
    "reading pause",
    "idle mouse drift",
    "click Learn more",
)


async def run(page: Page) -> None:
    n = len(STEP_LABELS)

    await run_verified_step(1, n, STEP_LABELS[0], lambda: _goto(page))
    await run_verified_step(2, n, STEP_LABELS[1], lambda: reading_pause(0.8, 2.0))
    await run_verified_step(3, n, STEP_LABELS[2], lambda: idle_mouse_drift(page))
    loc = resolve_locator(page, by="role", role="link", name="Learn more")
    await loc.wait_for(state="visible", timeout=15_000)
    await run_verified_step(4, n, STEP_LABELS[3], lambda: human_click(page, loc))


async def _goto(page: Page) -> None:
    await page.goto("https://example.com", wait_until="domcontentloaded")
