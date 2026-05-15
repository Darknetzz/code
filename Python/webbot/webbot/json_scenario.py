"""Execute JSON-defined scenario steps with human-like behavior."""

from __future__ import annotations

from collections.abc import Callable

from playwright.async_api import Locator, Page

from webbot.human import human_click, human_delay, human_scroll, reading_pause
from webbot.models import (
    ClickStep,
    DelayStep,
    GotoStep,
    ScenarioDocument,
    ScrollStep,
    Step,
)
from webbot.run_context import run_verified_step
from webbot.scenario_store import load_json_scenario


def step_label(step: Step) -> str:
    if isinstance(step, GotoStep):
        return f"goto {step.url}"
    if isinstance(step, DelayStep):
        return f"delay {step.min}–{step.max}s"
    if isinstance(step, ScrollStep):
        dy = step.delta_y if step.delta_y is not None else "auto"
        return f"scroll (delta_y={dy})"
    if isinstance(step, ClickStep):
        target = step.role or step.text or step.selector or step.test_id or "?"
        extra = f' "{step.name}"' if step.name else ""
        return f"click {step.by} {target}{extra}"
    return step.action  # type: ignore[union-attr]


def resolve_locator(page: Page, step: ClickStep) -> Locator:
    if step.by == "role":
        if not step.role:
            raise ValueError("click step with by=role requires 'role'")
        return page.get_by_role(step.role, name=step.name or None)
    if step.by == "text":
        if not step.text:
            raise ValueError("click step with by=text requires 'text'")
        return page.get_by_text(step.text)
    if step.by == "css":
        if not step.selector:
            raise ValueError("click step with by=css requires 'selector'")
        return page.locator(step.selector)
    if step.by == "test_id":
        if not step.test_id:
            raise ValueError("click step with by=test_id requires 'test_id'")
        return page.get_by_test_id(step.test_id)
    raise ValueError(f"Unknown locator by: {step.by}")


async def execute_step(page: Page, step: Step) -> None:
    if isinstance(step, GotoStep):
        await page.goto(step.url, wait_until="domcontentloaded")
        await reading_pause(0.8, 2.0)
    elif isinstance(step, DelayStep):
        await human_delay(step.min, step.max)
    elif isinstance(step, ScrollStep):
        await human_scroll(page, delta_y=step.delta_y, steps=step.steps)
    elif isinstance(step, ClickStep):
        loc = resolve_locator(page, step)
        await loc.wait_for(state="visible", timeout=15_000)
        await human_click(page, loc)
    else:
        raise ValueError(f"Unknown step: {step}")


async def run_json_scenario(
    page: Page,
    doc: ScenarioDocument,
    *,
    log: Callable[[str], None] | None = None,
) -> None:
    if doc.start_url and not any(isinstance(s, GotoStep) for s in doc.steps):
        total = len(doc.steps) + 1
        await run_verified_step(
            1,
            total,
            f"goto {doc.start_url}",
            lambda: _goto_start(page, doc.start_url),
        )
        step_offset = 1
    else:
        total = len(doc.steps)
        step_offset = 0

    for i, step in enumerate(doc.steps, start=1):
        idx = i + step_offset
        label = step_label(step)
        await run_verified_step(idx, total, label, lambda s=step: execute_step(page, s))


async def _goto_start(page: Page, url: str) -> None:
    await page.goto(url, wait_until="domcontentloaded")
    await reading_pause(0.8, 2.0)


def make_json_runner(name: str):
    async def _run(page: Page) -> None:
        doc = load_json_scenario(name)
        await run_json_scenario(page, doc)

    return _run
