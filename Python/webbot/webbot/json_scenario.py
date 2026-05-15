"""Execute JSON-defined scenario steps with human-like behavior."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from webbot.exceptions import WorkflowExit
from webbot.human import ScrollOptions, human_click, human_delay, human_fill, human_scroll, reading_pause
from webbot.locators import resolve_locator
from webbot.models import (
    ClickStep,
    DelayStep,
    ExitStep,
    FillStep,
    FormField,
    IfPresentStep,
    OpenUrlStep,
    RunScenarioStep,
    ScenarioDocument,
    ScrollStep,
    Step,
    SubmitFormStep,
    WorkflowGotoStep,
)
from webbot.run_context import get_run_context, run_verified_step
from webbot.scenario_store import load_json_scenario, scenario_kind

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
    wl = (getattr(step, "workflow_label", None) or "").strip()
    wl_s = f" @{wl}" if wl else ""
    if isinstance(step, OpenUrlStep):
        return f"open URL {step.url}{wl_s}"
    if isinstance(step, WorkflowGotoStep):
        return f"goto › {step.goto_label}{wl_s}"
    if isinstance(step, DelayStep):
        extra = f" ({step.distribution})" if step.distribution != "uniform" else ""
        return f"delay {step.min}-{step.max}s{extra}{wl_s}"
    if isinstance(step, ScrollStep):
        dy = step.delta_y if step.delta_y is not None else "auto"
        os = " +overscroll" if step.overscroll else ""
        return f"scroll dy={dy}{os}{wl_s}"
    if isinstance(step, FillStep):
        target = step.selector or step.label or step.name or step.role or "?"
        return f"fill {target} = {step.value!r}{wl_s}"
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
        return f"click {step.by} {target}{extra}{wl_s}"
    if isinstance(step, SubmitFormStep):
        n = len(step.fields)
        return f"submit_form ({step.method.upper()}) {n} field(s){wl_s}"
    if isinstance(step, RunScenarioStep):
        return f"run scenario: {step.scenario}{wl_s}"
    if isinstance(step, IfPresentStep):
        target = (
            step.role
            or step.text
            or step.selector
            or step.data_value
            or step.test_id
            or "?"
        )
        extra = f' "{step.name}"' if step.name else ""
        return f"if_present {step.by} {target}{extra} ({step.timeout_ms}ms){wl_s}"
    if isinstance(step, ExitStep):
        return f"exit{': ' + step.message if step.message.strip() else ''}{wl_s}"
    return f"{step.action}{wl_s}"


def _needs_implicit_goto(doc: ScenarioDocument, skip_implicit_start_url: bool) -> bool:
    return (
        bool(doc.start_url)
        and not document_has_explicit_open_url(doc.steps)
        and not skip_implicit_start_url
    )


def document_has_explicit_open_url(steps: list[Step]) -> bool:
    """True when steps already navigate (recursive), so ``start_url`` is not injected implicitly."""

    for step in steps:
        if isinstance(step, OpenUrlStep):
            return True
        if isinstance(step, IfPresentStep):
            if document_has_explicit_open_url(step.then_steps) or document_has_explicit_open_url(
                step.else_steps
            ):
                return True
    return False


def validate_workflow_jump_constraints(doc: ScenarioDocument) -> None:
    """Ensure unique ``workflow_label`` anchors and forward-only ``goto`` within each step list."""

    _validate_workflow_jump_step_list(doc.steps, context=f"scenario {doc.name!r} (root)")


def _validate_workflow_jump_step_list(steps: list[Step], *, context: str) -> None:
    anchors: dict[str, int] = {}
    for i, st in enumerate(steps):
        raw = getattr(st, "workflow_label", None)
        lab = raw.strip() if isinstance(raw, str) else ""
        if lab:
            if lab in anchors:
                prev = anchors[lab]
                raise ValueError(f"Duplicate workflow_label {lab!r} in {context}: indices {prev} and {i}.")
            anchors[lab] = i

    for i, st in enumerate(steps):
        if isinstance(st, WorkflowGotoStep):
            gl = st.goto_label.strip()
            if gl not in anchors:
                raise ValueError(
                    f"goto step at index {i} in {context} references unknown label {gl!r} "
                    "(set workflow_label on a later step in the same list)."
                )
            ti = anchors[gl]
            if ti <= i:
                raise ValueError(
                    f"goto in {context} at index {i} must target a later step; "
                    f"label {gl!r} is at index {ti}."
                )
        if isinstance(st, IfPresentStep):
            _validate_workflow_jump_step_list(st.then_steps, context=f"{context} › if_present then")
            _validate_workflow_jump_step_list(st.else_steps, context=f"{context} › if_present else")


def _workflow_dispatch_weights(
    steps: list[Step],
    *,
    scenario_name: str,
    stack: frozenset[str],
    label_prefix: str,
    depth: int,
) -> list[int]:
    return [
        _flattened_label_count_for_steps(
            [st], scenario_name=scenario_name, stack=stack, label_prefix=label_prefix, depth=depth
        )
        for st in steps
    ]


def _anchors_for_jump_targets(steps: list[Step]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, st in enumerate(steps):
        raw = getattr(st, "workflow_label", None)
        lab = raw.strip() if isinstance(raw, str) else ""
        if lab:
            out[lab] = i
    return out
    labels: list[str],
    step: Step,
    *,
    scenario_name: str,
    stack: frozenset[str],
    label_prefix: str,
    depth: int,
) -> None:
    """Append flattened plan rows for one step (including nested ``run_scenario`` / ``if_present``)."""
    if depth > MAX_SCENARIO_NEST_DEPTH:
        raise ValueError(f"Scenario nesting exceeds maximum depth ({MAX_SCENARIO_NEST_DEPTH})")

    if isinstance(step, RunScenarioStep):
        sub = step.scenario.strip()
        if not sub:
            raise ValueError("run_scenario step has an empty scenario name")
        if sub == scenario_name or sub in stack:
            raise ValueError(f"Scenario cycle detected involving '{scenario_name}' -> '{sub}'")
        nest_prefix = label_prefix + f"[{sub}] "
        sk = scenario_kind(sub)
        if sk == "python":
            labels.append(nest_prefix + f"run python scenario: {sub}")
        elif sk == "json":
            nested = load_json_scenario(sub)
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
            raise ValueError(f"Unknown scenario: {sub}")
        return

    if isinstance(step, IfPresentStep):
        labels.append(label_prefix + step_label(step))
        then_p = label_prefix + "[if › then] "
        for s in step.then_steps:
            _append_labels_for_step(
                labels, s, scenario_name=scenario_name, stack=stack, label_prefix=then_p, depth=depth + 1
            )
        else_p = label_prefix + "[if › else] "
        for s in step.else_steps:
            _append_labels_for_step(
                labels, s, scenario_name=scenario_name, stack=stack, label_prefix=else_p, depth=depth + 1
            )
        return

    labels.append(label_prefix + step_label(step))


def _flattened_label_count_for_steps(
    steps: list[Step],
    *,
    scenario_name: str,
    stack: frozenset[str],
    label_prefix: str,
    depth: int,
) -> int:
    buf: list[str] = []
    for s in steps:
        _append_labels_for_step(buf, s, scenario_name=scenario_name, stack=stack, label_prefix=label_prefix, depth=depth)
    return len(buf)


def collect_expanded_plan_labels(
    doc: ScenarioDocument,
    *,
    scenario_name: str,
    stack: frozenset[str],
    skip_implicit_start_url: bool,
    label_prefix: str,
    depth: int,
) -> list[str]:
    """Flatten nested ``run_scenario`` / ``if_present`` into ordered preview/run labels."""
    if depth > MAX_SCENARIO_NEST_DEPTH:
        raise ValueError(f"Scenario nesting exceeds maximum depth ({MAX_SCENARIO_NEST_DEPTH})")

    labels: list[str] = []
    if _needs_implicit_goto(doc, skip_implicit_start_url):
        labels.append(label_prefix + f"open URL {doc.start_url}")

    for step in doc.steps:
        _append_labels_for_step(
            labels, step, scenario_name=scenario_name, stack=stack, label_prefix=label_prefix, depth=depth
        )
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

    def skip_plan_steps(self, count: int) -> None:
        """Advance the flat plan index without executing (unused ``if_present`` branch)."""
        if count <= 0:
            return
        ctx = get_run_context()
        for _ in range(count):
            self._i += 1
            if self._i > len(self._plan):
                raise RuntimeError("Scenario plan index overflow (if_present branch sizing bug)")
            idx = self._i
            label = self._plan[idx - 1]
            if ctx:
                ctx.skip_step(idx, self.total(), label)


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


def _loc_kwargs_if_present(step: IfPresentStep) -> dict:
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


async def _locator_visible_if_present(page: Page, step: IfPresentStep) -> bool:
    loc = resolve_locator(page, **_loc_kwargs_if_present(step))
    try:
        if step.timeout_ms <= 0:
            if await loc.count() == 0:
                return False
            try:
                return await loc.first.is_visible()
            except Exception:
                return False
        await loc.first.wait_for(state="visible", timeout=float(step.timeout_ms))
        return True
    except PlaywrightTimeoutError:
        return False


async def execute_step(page: Page, step: Step) -> None:
    if isinstance(step, OpenUrlStep):
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
    elif isinstance(step, ExitStep):
        msg = step.message.strip()
        ctx = get_run_context()
        if msg and ctx:
            ctx._log(msg)
        raise WorkflowExit(msg)
    elif isinstance(step, RunScenarioStep):
        raise ValueError(
            "run_scenario steps must be executed via run_json_scenario (nested expansion)"
        )
    elif isinstance(step, IfPresentStep):
        raise ValueError(
            "if_present steps must be executed via the JSON scenario runner (branch handling)"
        )
    elif isinstance(step, WorkflowGotoStep):
        raise ValueError(
            "goto (workflow jump) steps must be executed via _run_step_sequence (runner handles jumps)"
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
    validate_workflow_jump_constraints(doc)
    labels = collect_expanded_plan_labels(
        doc,
        scenario_name=name,
        stack=frozenset(),
        skip_implicit_start_url=False,
        label_prefix="",
        depth=0,
    )
    return [(i + 1, lab) for i, lab in enumerate(labels)]


async def _run_step_sequence(
    page: Page,
    steps: list[Step],
    *,
    scenario_name: str,
    stack: frozenset[str],
    delay_doc: ScenarioDocument,
    label_prefix: str,
    depth: int,
    tracker: JsonRunTracker,
) -> None:
    if not steps:
        return

    anchors = _anchors_for_jump_targets(steps)
    weights = _workflow_dispatch_weights(
        steps, scenario_name=scenario_name, stack=stack, label_prefix=label_prefix, depth=depth
    )

    idx = 0
    executed_sub = False

    while idx < len(steps):
        s = steps[idx]
        if executed_sub:
            await _between_steps_pause(delay_doc)
        executed_sub = True

        if isinstance(s, WorkflowGotoStep):
            gl = s.goto_label.strip()
            tgt_ix = anchors[gl]
            if tgt_ix <= idx:
                raise RuntimeError("workflow goto index mismatch (should have been validated)")
            skip = sum(weights[idx + 1 : tgt_ix])

            async def _noop() -> None:
                await asyncio.sleep(0)

            await tracker.verified_step(_noop)
            tracker.skip_plan_steps(skip)
            idx = tgt_ix
            continue

        await dispatch_json_step(
            page,
            s,
            scenario_name=scenario_name,
            stack=stack,
            delay_doc=delay_doc,
            label_prefix=label_prefix,
            depth=depth,
            tracker=tracker,
        )
        idx += 1


async def _execute_if_present(
    page: Page,
    step: IfPresentStep,
    *,
    scenario_name: str,
    stack: frozenset[str],
    delay_doc: ScenarioDocument,
    label_prefix: str,
    depth: int,
    tracker: JsonRunTracker,
) -> None:
    sight: dict[str, bool] = {}

    async def check() -> None:
        sight["present"] = await _locator_visible_if_present(page, step)

    await tracker.verified_step(check)
    present = sight.get("present", False)

    then_p = label_prefix + "[if › then] "
    else_p = label_prefix + "[if › else] "
    then_n = _flattened_label_count_for_steps(
        step.then_steps,
        scenario_name=scenario_name,
        stack=stack,
        label_prefix=then_p,
        depth=depth + 1,
    )
    else_n = _flattened_label_count_for_steps(
        step.else_steps,
        scenario_name=scenario_name,
        stack=stack,
        label_prefix=else_p,
        depth=depth + 1,
    )

    if present:
        await _run_step_sequence(
            page,
            step.then_steps,
            scenario_name=scenario_name,
            stack=stack,
            delay_doc=delay_doc,
            label_prefix=then_p,
            depth=depth + 1,
            tracker=tracker,
        )
        tracker.skip_plan_steps(else_n)
    else:
        tracker.skip_plan_steps(then_n)
        await _run_step_sequence(
            page,
            step.else_steps,
            scenario_name=scenario_name,
            stack=stack,
            delay_doc=delay_doc,
            label_prefix=else_p,
            depth=depth + 1,
            tracker=tracker,
        )


async def dispatch_json_step(
    page: Page,
    step: Step,
    *,
    scenario_name: str,
    stack: frozenset[str],
    delay_doc: ScenarioDocument,
    label_prefix: str,
    depth: int,
    tracker: JsonRunTracker,
) -> None:
    if isinstance(step, RunScenarioStep):
        sub = step.scenario.strip()
        if not sub:
            raise ValueError("run_scenario step has an empty scenario name")
        if sub == scenario_name or sub in stack:
            raise ValueError(f"Scenario cycle detected involving '{scenario_name}' -> '{sub}'")
        sk = scenario_kind(sub)
        nest_prefix = label_prefix + f"[{sub}] "
        if sk == "python":
            from webbot.scenarios import get_scenario

            fn = get_scenario(sub)

            await tracker.verified_step(lambda: fn(page))
        elif sk == "json":
            nested = load_json_scenario(sub)
            nest_delay = delay_doc if step.inherit_delays else nested
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
            raise ValueError(f"Unknown scenario: {sub}")
        return

    if isinstance(step, IfPresentStep):
        await _execute_if_present(
            page,
            step,
            scenario_name=scenario_name,
            stack=stack,
            delay_doc=delay_doc,
            label_prefix=label_prefix,
            depth=depth,
            tracker=tracker,
        )
        return

    await tracker.verified_step(lambda s=step: execute_step(page, s))


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

        await dispatch_json_step(
            page,
            step,
            scenario_name=scenario_name,
            stack=stack,
            delay_doc=delay_doc,
            label_prefix=label_prefix,
            depth=depth,
            tracker=tracker,
        )


async def run_json_scenario(
    page: Page,
    doc: ScenarioDocument,
    *,
    log: Callable[[str], None] | None = None,
    root_name: str | None = None,
) -> None:
    del log  # retained for backward-compatible call sites
    name = root_name if root_name is not None else doc.name
    validate_workflow_jump_constraints(doc)
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
    try:
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
    except WorkflowExit:
        return


async def run_mixed_scenario_group(
    page: Page,
    *,
    group_label: str,
    scenario_names: list[str],
    pause_between_flows_sec: float,
) -> None:
    from webbot.scenarios import get_scenario

    labels = collect_group_plan_labels(group_label, scenario_names)

    ctx = get_run_context()
    if ctx:
        ctx.plan_steps([(i + 1, lab) for i, lab in enumerate(labels)])

    tracker = JsonRunTracker(labels)
    first_flow = True
    for sn in scenario_names:
        if not first_flow and pause_between_flows_sec > 0:
            await asyncio.sleep(pause_between_flows_sec)
        first_flow = False
        prefix = f"[{group_label} › {sn}] "
        sk = scenario_kind(sn)
        if sk == "json":
            doc = load_json_scenario(sn)
            try:
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
            except WorkflowExit:
                return
        elif sk == "python":
            try:
                fn = get_scenario(sn)
                await tracker.verified_step(lambda: fn(page))
            except WorkflowExit:
                return
        else:
            raise ValueError(f"Unknown scenario: {sn}")


def collect_group_plan_labels(group_label: str, scenario_names: list[str]) -> list[str]:
    labels: list[str] = []
    for sn in scenario_names:
        prefix = f"[{group_label} › {sn}] "
        sk = scenario_kind(sn)
        if sk == "json":
            doc = load_json_scenario(sn)
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
        elif sk == "python":
            labels.append(prefix + f"python scenario: {sn}")
        else:
            raise ValueError(f"Unknown scenario: {sn}")
    return labels


async def _goto_start(page: Page, url: str) -> None:
    await page.goto(url, wait_until="domcontentloaded")
    await reading_pause(0.8, 2.0)


def make_json_runner(name: str):
    async def _run(page: Page) -> None:
        doc = load_json_scenario(name)
        await run_json_scenario(page, doc, root_name=name)

    return _run
