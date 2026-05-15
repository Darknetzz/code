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
from webbot.scenario_store import load_json_scenario


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


async def execute_step(page: Page, step: Step, *, log: Callable[[str], None] | None = None) -> None:
    def _log(msg: str) -> None:
        if log:
            log(msg)

    if isinstance(step, GotoStep):
        _log(f"goto {step.url}")
        await page.goto(step.url, wait_until="domcontentloaded")
        await reading_pause(0.8, 2.0)
    elif isinstance(step, DelayStep):
        _log(f"delay {step.min}–{step.max}s")
        await human_delay(step.min, step.max)
    elif isinstance(step, ScrollStep):
        _log("scroll")
        await human_scroll(page, delta_y=step.delta_y, steps=step.steps)
    elif isinstance(step, ClickStep):
        loc = resolve_locator(page, step)
        _log(f"click {step.by} {step.role or step.text or step.selector or step.test_id}")
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
        await page.goto(doc.start_url, wait_until="domcontentloaded")
        await reading_pause(0.8, 2.0)

    for i, step in enumerate(doc.steps, start=1):
        if log:
            log(f"Step {i}/{len(doc.steps)}: {step.action}")
        await execute_step(page, step, log=log)


def make_json_runner(name: str):
    async def _run(page: Page) -> None:
        doc = load_json_scenario(name)
        await run_json_scenario(page, doc)

    return _run
