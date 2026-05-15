"""Execute JSON-defined scenario steps with human-like behavior."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from playwright.async_api import Locator, Page

from webbot.human import ScrollOptions, human_click, human_delay, human_fill, human_scroll, reading_pause
from webbot.locators import resolve_locator
from webbot.models import (
    ClickStep,
    DelayStep,
    FillStep,
    FormField,
    GotoStep,
    RunScenarioStep,
    ScenarioDocument,
    ScrollStep,
    Step,
    SubmitFormStep,
)
from webbot.run_context import get_run_context, run_verified_step
from webbot.scenario_store import load_json_scenario

MAX_SCENARIO_NEST_DEPTH = 16


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
    if isinstance(step, RunScenarioStep):
        return f"run scenario: {step.scenario}"
    return step.action  # type: ignore[union-attr]


def _needs_implicit_goto(doc: ScenarioDocument, skip_implicit_start_url: bool) -> bool:
    return (
        bool(doc.start_url)
        and not any(isinstance(s, GotoStep) for s in doc.steps)
        and not skip_implicit_start_url
    )


def collect_expanded_plan_labels(
    doc: ScenarioDocument,
    *,
    scenario_name: str,
    stack: frozenset[str],
    skip_implicit_start_url: bool,
    label_prefix: str,
    depth: int,
) -> list[str]:
    """Flatten nested ``run_scenario`` steps into ordered preview/run labels."""
    if depth > MAX_SCENARIO_NEST_DEPTH:
        raise ValueError(f"Scenario nesting exceeds maximum depth ({MAX_SCENARIO_NEST_DEPTH})")

    labels: list[str] = []
    if _needs_implicit_goto(doc, skip_implicit_start_url):
        labels.append(label_prefix + f"goto {doc.start_url}")

    for step in doc.steps:
        if isinstance(step, RunScenarioStep):
            sub = step.scenario.strip()
            if not sub:
                raise ValueError("run_scenario step has an empty scenario name")
            if sub == scenario_name or sub in stack:
                raise ValueError(f"Scenario cycle detected involving '{scenario_name}' -> '{sub}'")
            nested = load_json_scenario(sub)
            nest_prefix = label_prefix + f"[{sub}] "
            labels.extend(
                collect_expanded_plan_labels(
                    nested,
                    scenario_name=sub,
                    stack=stack | {scenario_name},
                    skip_implicit_start_url=step.skip_start_url,
                    label_prefix=nest_prefix,
                    depth=depth + 1,
                )
            )
        else:
            labels.append(label_prefix + step_label(step))
    return labels


class JsonRunTracker:
    """Assigns flattened plan indices to each verified browser step."""

    __slots__ = ("_plan", "_i")

    def __init__(self, plan: list[str]) -> None:
        self._plan = plan
        self._i = 0

    def total(self) -> int:
        return len(self._plan)

    async def verified_step(self, fn: Callable[[], Awaitable[None]]) -> None:
        self._i += 1
        idx = self._i
        label = self._plan[idx - 1]
        await run_verified_step(idx, self.total(), label, fn)


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
    elif isinstance(step, RunScenarioStep):
        raise ValueError(
            "run_scenario steps must be executed via run_json_scenario (nested expansion)"
        )
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


def build_step_plan(doc: ScenarioDocument, *, root_name: str | None = None) -> list[tuple[int, str]]:
    name = root_name if root_name is not None else doc.name
    labels = collect_expanded_plan_labels(
        doc,
        scenario_name=name,
        stack=frozenset(),
        skip_implicit_start_url=False,
        label_prefix="",
        depth=0,
    )
    return [(i + 1, lab) for i, lab in enumerate(labels)]


async def execute_json_document(
    page: Page,
    doc: ScenarioDocument,
    *,
    scenario_name: str,
    stack: frozenset[str],
    skip_implicit_start_url: bool,
    delay_doc: ScenarioDocument,
    label_prefix: str,
    depth: int,
    tracker: JsonRunTracker,
) -> None:
    if depth > MAX_SCENARIO_NEST_DEPTH:
        raise ValueError(f"Scenario nesting exceeds maximum depth ({MAX_SCENARIO_NEST_DEPTH})")

    executed = False
    if _needs_implicit_goto(doc, skip_implicit_start_url):
        url = doc.start_url
        await tracker.verified_step(lambda: _goto_start(page, url))
        executed = True

    for step in doc.steps:
        if executed:
            await _between_steps_pause(delay_doc)
        executed = True

        if isinstance(step, RunScenarioStep):
            sub = step.scenario.strip()
            if not sub:
                raise ValueError("run_scenario step has an empty scenario name")
            if sub == scenario_name or sub in stack:
                raise ValueError(f"Scenario cycle detected involving '{scenario_name}' -> '{sub}'")
            nested = load_json_scenario(sub)
            nest_delay = delay_doc if step.inherit_delays else nested
            nest_prefix = label_prefix + f"[{sub}] "
            await execute_json_document(
                page,
                nested,
                scenario_name=sub,
                stack=stack | {scenario_name},
                skip_implicit_start_url=step.skip_start_url,
                delay_doc=nest_delay,
                label_prefix=nest_prefix,
                depth=depth + 1,
                tracker=tracker,
            )
        else:
            await tracker.verified_step(lambda s=step: execute_step(page, s))


async def run_json_scenario(
    page: Page,
    doc: ScenarioDocument,
    *,
    log: Callable[[str], None] | None = None,
    root_name: str | None = None,
) -> None:
    del log  # retained for backward-compatible call sites
    name = root_name if root_name is not None else doc.name
    labels = collect_expanded_plan_labels(
        doc,
        scenario_name=name,
        stack=frozenset(),
        skip_implicit_start_url=False,
        label_prefix="",
        depth=0,
    )
    ctx = get_run_context()
    if ctx:
        ctx.plan_steps([(i + 1, lab) for i, lab in enumerate(labels)])

    tracker = JsonRunTracker(labels)
    await execute_json_document(
        page,
        doc,
        scenario_name=name,
        stack=frozenset(),
        skip_implicit_start_url=False,
        delay_doc=doc,
        label_prefix="",
        depth=0,
        tracker=tracker,
    )


async def run_json_scenario_group(
    page: Page,
    *,
    group_label: str,
    scenario_names: list[str],
    pause_between_flows_sec: float,
) -> None:
    labels: list[str] = []
    for sn in scenario_names:
        doc = load_json_scenario(sn)
        prefix = f"[{group_label} › {sn}] "
        labels.extend(
            collect_expanded_plan_labels(
                doc,
                scenario_name=sn,
                stack=frozenset(),
                skip_implicit_start_url=False,
                label_prefix=prefix,
                depth=0,
            )
        )

    ctx = get_run_context()
    if ctx:
        ctx.plan_steps([(i + 1, lab) for i, lab in enumerate(labels)])

    tracker = JsonRunTracker(labels)
    first_flow = True
    for sn in scenario_names:
        if not first_flow and pause_between_flows_sec > 0:
            await asyncio.sleep(pause_between_flows_sec)
        first_flow = False
        doc = load_json_scenario(sn)
        prefix = f"[{group_label} › {sn}] "
        await execute_json_document(
            page,
            doc,
            scenario_name=sn,
            stack=frozenset(),
            skip_implicit_start_url=False,
            delay_doc=doc,
            label_prefix=prefix,
            depth=0,
            tracker=tracker,
        )


async def _goto_start(page: Page, url: str) -> None:
    await page.goto(url, wait_until="domcontentloaded")
    await reading_pause(0.8, 2.0)


def make_json_runner(name: str):
    async def _run(page: Page) -> None:
        doc = load_json_scenario(name)
        await run_json_scenario(page, doc, root_name=name)

    return _run
