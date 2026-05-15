"""Pydantic models for JSON scenarios and API payloads."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, model_validator


class StepBase(BaseModel):
    """Optional anchor for ``goto`` steps within the same linear step list (root or one branch)."""

    workflow_label: str = ""


class OpenUrlStep(StepBase):
    action: Literal["open_url"] = "open_url"
    url: str


class WorkflowGotoStep(StepBase):
    """Jump forward to a later step in the same step list (must share the same parent array)."""

    action: Literal["goto"] = "goto"
    goto_label: str = Field(min_length=1)


class DelayStep(StepBase):
    action: Literal["delay"] = "delay"
    min: float = 0.3
    max: float = 1.2
    distribution: Literal["uniform", "triangular", "log_normal"] = "uniform"
    long_pause_chance: float = Field(default=0.0, ge=0.0, le=1.0)
    long_pause_min: float = 2.0
    long_pause_max: float = 5.0


class ScrollStep(StepBase):
    action: Literal["scroll"] = "scroll"
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


class ClickStep(StepBase):
    action: Literal["click"] = "click"
    by: Literal["role", "text", "css", "test_id", "data"] = "role"
    role: str | None = None
    name: str | None = None
    text: str | None = None
    selector: str | None = None
    test_id: str | None = None
    data_attr: str | None = None
    data_value: str | None = None


class FillStep(StepBase):
    """Fill a single input, textarea, or select."""

    action: Literal["fill"] = "fill"
    by: Literal["role", "text", "css", "test_id", "label", "data"] = "css"
    role: str | None = None
    name: str | None = None
    label: str | None = None
    text: str | None = None
    selector: str | None = None
    test_id: str | None = None
    data_attr: str | None = None
    data_value: str | None = None
    value: str


class FormField(BaseModel):
    by: Literal["role", "text", "css", "test_id", "label", "data"] = "css"
    role: str | None = None
    name: str | None = None
    label: str | None = None
    text: str | None = None
    selector: str | None = None
    test_id: str | None = None
    data_attr: str | None = None
    data_value: str | None = None
    value: str


class RunScenarioStep(StepBase):
    """Run another saved scenario inline (same browser session): JSON expands steps; Python runs as one block)."""

    action: Literal["run_scenario"] = "run_scenario"
    scenario: str
    inherit_delays: bool = False
    skip_start_url: bool = True


class IfPresentStep(StepBase):
    """If a locator matches (visible within timeout), run ``then_steps``; otherwise ``else_steps``."""

    action: Literal["if_present"] = "if_present"
    by: Literal["role", "text", "css", "test_id", "data"] = "role"
    role: str | None = None
    name: str | None = None
    text: str | None = None
    selector: str | None = None
    test_id: str | None = None
    data_attr: str | None = None
    data_value: str | None = None
    timeout_ms: int = Field(default=3000, ge=0)
    then_steps: list["Step"] = Field(default_factory=list)
    else_steps: list["Step"] = Field(default_factory=list)


class ExitStep(StepBase):
    """End the scenario run successfully without executing further steps."""

    action: Literal["exit"] = "exit"
    message: str = ""


class SubmitFormStep(StepBase):
    """Fill fields and submit a form (GET or POST per the form's method attribute)."""

    action: Literal["submit_form"] = "submit_form"
    method: Literal["get", "post"] = "post"
    form_selector: str | None = None
    fields: list[FormField] = Field(default_factory=list)
    submit_by: Literal["role", "text", "css", "test_id", "data", "form"] = "role"
    submit_role: str | None = "button"
    submit_name: str | None = None
    submit_text: str | None = None
    submit_selector: str | None = None
    submit_test_id: str | None = None
    submit_data_attr: str | None = None
    submit_data_value: str | None = None
    wait_for_navigation: bool = True


Step = Annotated[
    Union[
        OpenUrlStep,
        WorkflowGotoStep,
        DelayStep,
        ScrollStep,
        ClickStep,
        FillStep,
        SubmitFormStep,
        RunScenarioStep,
        IfPresentStep,
        ExitStep,
    ],
    Field(discriminator="action"),
]


class ScenarioDocument(BaseModel):
    name: str
    description: str = ""
    start_url: str = ""
    steps: list[Step] = Field(default_factory=list)
    random_delay_between_steps: bool = False
    between_steps_min: float = 0.3
    between_steps_max: float = 1.2
    between_steps_distribution: Literal["uniform", "triangular", "log_normal"] = "triangular"

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_navigation_goto(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        steps = data.get("steps")
        if isinstance(steps, list):
            data = {**data, "steps": [_migrate_legacy_step_payload(s) for s in steps]}
        return data


class ScenarioInfo(BaseModel):
    name: str
    type: Literal["json", "python"]
    description: str = ""


class ScenarioPreviewStep(BaseModel):
    index: int
    label: str


class ScenarioPreview(BaseModel):
    name: str
    type: Literal["json", "python"]
    description: str = ""
    steps: list[ScenarioPreviewStep] = Field(default_factory=list)
    source: str | None = None
    start_url: str | None = None
    random_delay_between_steps: bool = False
    between_steps_min: float = 0.3
    between_steps_max: float = 1.2
    between_steps_distribution: Literal["uniform", "triangular", "log_normal"] = "triangular"


class RunRequest(BaseModel):
    scenario: str
    loops: int = 1
    pause_between_loops_sec: float = 0.0
    headless: bool = False
    channel: str | None = "chrome"
    slow_mo: int = 0
    ignore_https_errors: bool = False


class FlowGroup(BaseModel):
    id: str
    label: str
    scenario_names: list[str] = Field(default_factory=list)


class GroupsDocument(BaseModel):
    groups: list[FlowGroup] = Field(default_factory=list)


class GroupsResponse(BaseModel):
    groups: list[FlowGroup]
    ungrouped: list[str]


class RunGroupRequest(BaseModel):
    group_id: str
    loops: int = 1
    pause_between_loops_sec: float = 0.0
    pause_between_flows_sec: float = 0.0
    headless: bool = False
    channel: str | None = "chrome"
    slow_mo: int = 0


class ScenarioStepPlanItem(BaseModel):
    index: int
    label: str


class ScenarioStepPlan(BaseModel):
    name: str
    steps: list[ScenarioStepPlanItem]


class PythonScenarioSource(BaseModel):
    """Raw editor payload for ``{name}.py`` scenarios."""

    name: str
    source: str
    description: str = ""


class PythonScenarioSave(BaseModel):
    source: str


class StepProgressItem(BaseModel):
    index: int
    label: str
    status: Literal["pending", "running", "ok", "failed", "skipped"] = "pending"
    error: str | None = None


class RunStatusResponse(BaseModel):
    state: str
    scenario: str | None = None
    loop: int = 0
    loops: int = 0
    step: int = 0
    steps: int = 0
    step_label: str | None = None
    error: str | None = None
    step_progress: list[StepProgressItem] = Field(default_factory=list)


def _migrate_legacy_step_payload(step: object) -> object:
    """Turn legacy ``goto`` URL steps into ``open_url`` before discriminated parsing."""
    if not isinstance(step, dict):
        return step
    out = dict(step)
    action = out.get("action")

    then_steps = out.get("then_steps")
    if isinstance(then_steps, list):
        out["then_steps"] = [_migrate_legacy_step_payload(s) for s in then_steps]

    else_steps = out.get("else_steps")
    if isinstance(else_steps, list):
        out["else_steps"] = [_migrate_legacy_step_payload(s) for s in else_steps]

    if action == "goto":
        goto_label_raw = out.get("goto_label")
        has_target = isinstance(goto_label_raw, str) and goto_label_raw.strip() != ""
        if has_target:
            return out  # Workflow goto (already new shape)
        if isinstance(out.get("url"), str) and str(out["url"]).strip() != "":
            out["action"] = "open_url"
            return out
        raise ValueError(
            "JSON step action 'goto' requires either legacy 'url' (use open_url) or non-empty goto_label "
            "(workflow goto)"
        )
    return out


ScenarioDocument.model_rebuild()
IfPresentStep.model_rebuild()
