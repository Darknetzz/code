"""Human-like delays, mouse paths, typing, and scrolling for Playwright."""

from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page


async def human_delay(min_sec: float = 0.3, max_sec: float = 1.2) -> None:
    await asyncio.sleep(random.uniform(min_sec, max_sec))


async def reading_pause(min_sec: float = 1.5, max_sec: float = 4.0) -> None:
    await asyncio.sleep(random.uniform(min_sec, max_sec))


def _bezier_point(t: float, p0: float, p1: float, p2: float, p3: float) -> float:
    u = 1 - t
    return u**3 * p0 + 3 * u**2 * t * p1 + 3 * u * t**2 * p2 + t**3 * p3


def _bezier_path(
    start: tuple[float, float],
    end: tuple[float, float],
    steps: int,
) -> list[tuple[float, float]]:
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    cp1 = (sx + dx * random.uniform(0.1, 0.4) + random.uniform(-30, 30), sy + dy * random.uniform(0.0, 0.3) + random.uniform(-20, 20))
    cp2 = (sx + dx * random.uniform(0.6, 0.9) + random.uniform(-30, 30), sy + dy * random.uniform(0.7, 1.0) + random.uniform(-20, 20))
    points: list[tuple[float, float]] = []
    for i in range(1, steps + 1):
        t = i / steps
        x = _bezier_point(t, sx, cp1[0], cp2[0], ex)
        y = _bezier_point(t, sy, cp1[1], cp2[1], ey)
        points.append((x + random.uniform(-1.5, 1.5), y + random.uniform(-1.5, 1.5)))
    return points


async def move_mouse_human(
    page: Page,
    x: float,
    y: float,
    *,
    start: tuple[float, float] | None = None,
) -> None:
    if start is None:
        start = (random.uniform(100, 400), random.uniform(100, 300))
    distance = ((x - start[0]) ** 2 + (y - start[1]) ** 2) ** 0.5
    steps = max(8, min(40, int(distance / 15)))
    for px, py in _bezier_path(start, (x, y), steps):
        await page.mouse.move(px, py)
        await asyncio.sleep(random.uniform(0.005, 0.025))


async def idle_mouse_drift(page: Page) -> None:
    x = random.uniform(200, 600)
    y = random.uniform(150, 450)
    await move_mouse_human(page, x, y)
    await asyncio.sleep(random.uniform(0.2, 0.8))


async def _target_point(locator: Locator) -> tuple[float, float]:
    box = await locator.bounding_box()
    if not box:
        raise RuntimeError("Element has no bounding box — is it visible?")
    x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
    y = box["y"] + box["height"] * random.uniform(0.3, 0.7)
    return x, y


async def human_click(page: Page, locator: Locator) -> None:
    await locator.scroll_into_view_if_needed()
    await human_delay(0.1, 0.4)
    x, y = await _target_point(locator)
    await move_mouse_human(page, x, y)
    await asyncio.sleep(random.uniform(0.05, 0.2))
    await page.mouse.click(x, y)
    await human_delay(0.2, 0.6)


async def human_type(page: Page, locator: Locator, text: str) -> None:
    await human_click(page, locator)
    for char in text:
        await page.keyboard.type(char, delay=random.randint(50, 150))
        if char in " .,;:" and random.random() < 0.15:
            await asyncio.sleep(random.uniform(0.1, 0.35))
    await human_delay(0.2, 0.5)


async def human_fill(page: Page, locator: Locator, text: str) -> None:
    await human_click(page, locator)
    await page.keyboard.press("Control+A")
    await asyncio.sleep(random.uniform(0.05, 0.15))
    for char in text:
        await page.keyboard.type(char, delay=random.randint(50, 150))
    await human_delay(0.2, 0.5)


async def human_scroll(
    page: Page,
    *,
    delta_y: int | None = None,
    steps: int | None = None,
) -> None:
    total = delta_y if delta_y is not None else random.randint(200, 500)
    step_count = steps or random.randint(3, 7)
    per_step = total // step_count
    for _ in range(step_count):
        await page.mouse.wheel(0, per_step + random.randint(-10, 10))
        await asyncio.sleep(random.uniform(0.08, 0.25))
    await human_delay(0.3, 0.8)
