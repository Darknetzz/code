"""Human-like delays, mouse paths, typing, and scrolling for Playwright."""

from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page

DelayDistribution = Literal["uniform", "triangular", "log_normal"]


def _sample_delay(
    min_sec: float,
    max_sec: float,
    distribution: DelayDistribution = "uniform",
) -> float:
    if max_sec <= min_sec:
        return min_sec
    if distribution == "triangular":
        # Skew toward shorter waits, occasional longer tail
        return random.triangular(min_sec, max_sec, min_sec + (max_sec - min_sec) * 0.35)
    if distribution == "log_normal":
        # Heavy tail: mostly short, sometimes much longer
        mu = math.log(min_sec + (max_sec - min_sec) * 0.25)
        sigma = 0.45
        return min(max_sec, max(min_sec, random.lognormvariate(mu, sigma)))
    return random.uniform(min_sec, max_sec)


async def human_delay(
    min_sec: float = 0.3,
    max_sec: float = 1.2,
    *,
    distribution: DelayDistribution = "uniform",
    long_pause_chance: float = 0.0,
    long_pause_min: float = 2.0,
    long_pause_max: float = 5.0,
) -> None:
    await asyncio.sleep(_sample_delay(min_sec, max_sec, distribution))
    if long_pause_chance > 0 and random.random() < long_pause_chance:
        await asyncio.sleep(random.uniform(long_pause_min, long_pause_max))


async def reading_pause(
    min_sec: float = 1.5,
    max_sec: float = 4.0,
    *,
    distribution: DelayDistribution = "triangular",
) -> None:
    await asyncio.sleep(_sample_delay(min_sec, max_sec, distribution))


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


@dataclass
class ScrollOptions:
    delta_y: int | None = None
    steps: int | None = None
    steps_min: int = 3
    steps_max: int = 8
    step_delay_min: float = 0.06
    step_delay_max: float = 0.32
    overscroll: bool = True
    overscroll_min: int | None = None
    overscroll_max: int | None = None
    overscroll_ratio_min: float = 0.06
    overscroll_ratio_max: float = 0.16
    pause_after_min: float = 0.2
    pause_after_max: float = 0.85
    variable_step_size: bool = True


async def _wheel_chunks(
    page: Page,
    total: int,
    step_count: int,
    *,
    step_delay_min: float,
    step_delay_max: float,
    variable_step_size: bool,
) -> None:
    if step_count <= 0:
        return
    sign = 1 if total >= 0 else -1
    remaining = abs(total)
    for i in range(step_count):
        if i == step_count - 1:
            chunk = remaining
        elif variable_step_size:
            chunk = max(1, int(remaining * random.uniform(0.15, 0.45)))
        else:
            chunk = max(1, remaining // (step_count - i))
        remaining -= chunk
        await page.mouse.wheel(0, sign * chunk)
        await asyncio.sleep(random.uniform(step_delay_min, step_delay_max))
        if remaining <= 0:
            break


async def human_scroll(
    page: Page,
    *,
    delta_y: int | None = None,
    steps: int | None = None,
    steps_min: int = 3,
    steps_max: int = 8,
    step_delay_min: float = 0.06,
    step_delay_max: float = 0.32,
    overscroll: bool = True,
    overscroll_min: int | None = None,
    overscroll_max: int | None = None,
    overscroll_ratio_min: float = 0.06,
    overscroll_ratio_max: float = 0.16,
    pause_after_min: float = 0.2,
    pause_after_max: float = 0.85,
    variable_step_size: bool = True,
    options: ScrollOptions | None = None,
) -> None:
    """Scroll with variable speed, optional overshoot-and-correct."""
    opts = options or ScrollOptions(
        delta_y=delta_y,
        steps=steps,
        steps_min=steps_min,
        steps_max=steps_max,
        step_delay_min=step_delay_min,
        step_delay_max=step_delay_max,
        overscroll=overscroll,
        overscroll_min=overscroll_min,
        overscroll_max=overscroll_max,
        overscroll_ratio_min=overscroll_ratio_min,
        overscroll_ratio_max=overscroll_ratio_max,
        pause_after_min=pause_after_min,
        pause_after_max=pause_after_max,
        variable_step_size=variable_step_size,
    )

    total = opts.delta_y if opts.delta_y is not None else random.randint(200, 500)
    if opts.steps is not None:
        step_count = max(1, opts.steps)
    else:
        lo, hi = min(opts.steps_min, opts.steps_max), max(opts.steps_min, opts.steps_max)
        step_count = random.randint(lo, hi)

    await _wheel_chunks(
        page,
        total,
        step_count,
        step_delay_min=opts.step_delay_min,
        step_delay_max=opts.step_delay_max,
        variable_step_size=opts.variable_step_size,
    )

    if opts.overscroll and total != 0:
        if opts.overscroll_min is not None and opts.overscroll_max is not None:
            overshoot = random.randint(
                min(opts.overscroll_min, opts.overscroll_max),
                max(opts.overscroll_min, opts.overscroll_max),
            )
        else:
            ratio = random.uniform(opts.overscroll_ratio_min, opts.overscroll_ratio_max)
            overshoot = max(8, int(abs(total) * ratio))

        sign = 1 if total > 0 else -1
        await asyncio.sleep(random.uniform(0.08, 0.22))
        await _wheel_chunks(
            page,
            sign * overshoot,
            random.randint(1, 3),
            step_delay_min=opts.step_delay_min * 0.8,
            step_delay_max=opts.step_delay_max * 0.9,
            variable_step_size=True,
        )
        await asyncio.sleep(random.uniform(0.12, 0.35))
        await _wheel_chunks(
            page,
            -sign * overshoot,
            random.randint(2, 4),
            step_delay_min=opts.step_delay_min,
            step_delay_max=opts.step_delay_max,
            variable_step_size=True,
        )

    await asyncio.sleep(random.uniform(opts.pause_after_min, opts.pause_after_max))
