"""Pydantic models for JSON scenarios and API payloads."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class GotoStep(BaseModel):
    action: Literal["goto"] = "goto"
    url: str


class DelayStep(BaseModel):
    action: Literal["delay"] = "delay"
    min: float = 0.3
    max: float = 1.2
    distribution: Literal["uniform", "triangular", "log_normal"] = "uniform"
    long_pause_chance: float = Field(default=0.0, ge=0.0, le=1.0)
    long_pause_min: float = 2.0
    long_pause_max: float = 5.0


class ScrollStep(BaseModel):
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


class ClickStep(BaseModel):
    action: Literal["click"] = "click"
    by: Literal["role", "text", "css", "test_id", "data"] = "role"
    role: str | None = None
    name: str | None = None
    text: str | None = None
    selector: str | None = None
    test_id: str | None = None
    data_attr: str | None = None
    data_value: str | None = None


class FillStep(BaseModel):
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


class RunScenarioStep(BaseModel):
    """Run another saved scenario inline (same browser session): JSON expands steps; Python runs as one block)."""

    action: Literal["run_scenario"] = "run_scenario"
    scenario: str
    inherit_delays: bool = False
    skip_start_url: bool = True


class SubmitFormStep(BaseModel):
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
    Union[GotoStep, DelayStep, ScrollStep, ClickStep, FillStep, SubmitFormStep, RunScenarioStep],
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
    status: Literal["pending", "running", "ok", "failed"] = "pending"
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
