"""Execute JSON-defined scenario steps with human-like behavior."""

from __future__ import annotations

from collections.abc import Callable

from playwright.async_api import Locator, Page

from webbot.human import ScrollOptions, human_click, human_delay, human_fill, human_scroll, reading_pause
from webbot.locators import resolve_locator
from webbot.models import (
    ClickStep,
    DelayStep,
    FillStep,
    FormField,
    GotoStep,
    ScenarioDocument,
    ScrollStep,
    Step,
    SubmitFormStep,
)
from webbot.run_context import get_run_context, run_verified_step
from webbot.scenario_store import load_json_scenario


def _loc_kwargs_field(field: FormField) -> dict:
    return {
        "by": field.by,
        "role": field.role,
        "name": field.name,
        "label": field.label,
        "text": field.text,
        "selector": field.selector,
        "test_id": field.test_id,
        "data_attr": field.data_attr,
        "data_value": field.data_value,
    }


def _loc_kwargs_click(step: ClickStep) -> dict:
    return {
        "by": step.by,
        "role": step.role,
        "name": step.name,
        "text": step.text,
        "selector": step.selector,
        "test_id": step.test_id,
        "data_attr": step.data_attr,
        "data_value": step.data_value,
    }


def step_label(step: Step) -> str:
    if isinstance(step, GotoStep):
        return f"goto {step.url}"
    if isinstance(step, DelayStep):
        extra = f" ({step.distribution})" if step.distribution != "uniform" else ""
        return f"delay {step.min}-{step.max}s{extra}"
    if isinstance(step, ScrollStep):
        dy = step.delta_y if step.delta_y is not None else "auto"
        os = " +overscroll" if step.overscroll else ""
        return f"scroll dy={dy}{os}"
    if isinstance(step, FillStep):
        target = step.selector or step.label or step.name or step.role or "?"
        return f"fill {target} = {step.value!r}"
    if isinstance(step, ClickStep):
        target = (
            step.role
            or step.text
            or step.selector
            or step.data_value
            or step.test_id
            or "?"
        )
        extra = f' "{step.name}"' if step.name else ""
        return f"click {step.by} {target}{extra}"
    if isinstance(step, SubmitFormStep):
        n = len(step.fields)
        return f"submit_form ({step.method.upper()}) {n} field(s)"
    return step.action  # type: ignore[union-attr]


async def _fill_field(page: Page, field: FormField) -> None:
    loc = resolve_locator(page, **_loc_kwargs_field(field))
    await loc.wait_for(state="visible", timeout=15_000)
    tag = await loc.evaluate("el => el.tagName.toLowerCase()")
    if tag == "select":
        await loc.select_option(value=field.value)
        await human_delay(0.2, 0.5)
    else:
        await human_fill(page, loc, field.value)


async def _verify_form_method(form_loc: Locator, expected: str) -> None:
    raw = await form_loc.get_attribute("method")
    actual = (raw or "get").strip().lower()
    expected_l = expected.lower()
    if actual != expected_l:
        raise ValueError(
            f"Form method is {actual!r} but step expects {expected_l!r}. "
            "Check form_selector or method on the step."
        )


async def execute_submit_form(page: Page, step: SubmitFormStep) -> None:
    form_loc: Locator | None = None
    if step.form_selector:
        form_loc = page.locator(step.form_selector)
        await form_loc.wait_for(state="visible", timeout=15_000)
        await _verify_form_method(form_loc, step.method)

    for field in step.fields:
        await _fill_field(page, field)

    if step.submit_by == "form":
        if not form_loc:
            raise ValueError("submit_by=form requires form_selector")
        nav = page.expect_navigation(wait_until="domcontentloaded", timeout=30_000)
        async with nav:
            await form_loc.evaluate("form => form.submit()")
    else:
        submit_loc = resolve_locator(
            page,
            by=step.submit_by,
            role=step.submit_role,
            name=step.submit_name,
            text=step.submit_text,
            selector=step.submit_selector,
            test_id=step.submit_test_id,
            data_attr=step.submit_data_attr,
            data_value=step.submit_data_value,
        )
        await submit_loc.wait_for(state="visible", timeout=15_000)
        if step.wait_for_navigation:
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=30_000):
                await human_click(page, submit_loc)
        else:
            await human_click(page, submit_loc)

    await reading_pause(0.5, 1.5)


async def execute_step(page: Page, step: Step) -> None:
    if isinstance(step, GotoStep):
        await page.goto(step.url, wait_until="domcontentloaded")
        await reading_pause(0.8, 2.0)
    elif isinstance(step, DelayStep):
        await human_delay(
            step.min,
            step.max,
            distribution=step.distribution,
            long_pause_chance=step.long_pause_chance,
            long_pause_min=step.long_pause_min,
            long_pause_max=step.long_pause_max,
        )
    elif isinstance(step, ScrollStep):
        await human_scroll(
            page,
            options=ScrollOptions(
                delta_y=step.delta_y,
                steps=step.steps,
                steps_min=step.steps_min,
                steps_max=step.steps_max,
                step_delay_min=step.step_delay_min,
                step_delay_max=step.step_delay_max,
                overscroll=step.overscroll,
                overscroll_min=step.overscroll_min,
                overscroll_max=step.overscroll_max,
                overscroll_ratio_min=step.overscroll_ratio_min,
                overscroll_ratio_max=step.overscroll_ratio_max,
                pause_after_min=step.pause_after_min,
                pause_after_max=step.pause_after_max,
                variable_step_size=step.variable_step_size,
            ),
        )
    elif isinstance(step, FillStep):
        await _fill_field(
            page,
            FormField(
                by=step.by,
                role=step.role,
                name=step.name,
                label=step.label,
                text=step.text,
                selector=step.selector,
                test_id=step.test_id,
                value=step.value,
            ),
        )
    elif isinstance(step, ClickStep):
        loc = resolve_locator(page, **_loc_kwargs_click(step))
        await loc.wait_for(state="visible", timeout=15_000)
        await human_click(page, loc)
    elif isinstance(step, SubmitFormStep):
        await execute_submit_form(page, step)
    else:
        raise ValueError(f"Unknown step: {step}")


async def _between_steps_pause(doc: ScenarioDocument) -> None:
    if not doc.random_delay_between_steps:
        return
    ctx = get_run_context()
    label = f"between steps ({doc.between_steps_min}-{doc.between_steps_max}s)"
    if ctx:
        ctx._log(f"[..] {label}")
    await human_delay(
        doc.between_steps_min,
        doc.between_steps_max,
        distribution=doc.between_steps_distribution,
    )
    if ctx:
        ctx._log(f"[OK] {label}")


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
        if idx > 1:
            await _between_steps_pause(doc)
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
