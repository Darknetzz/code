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


class ScrollStep(BaseModel):
    action: Literal["scroll"] = "scroll"
    delta_y: int | None = None
    steps: int | None = None


class ClickStep(BaseModel):
    action: Literal["click"] = "click"
    by: Literal["role", "text", "css", "test_id"] = "role"
    role: str | None = None
    name: str | None = None
    text: str | None = None
    selector: str | None = None
    test_id: str | None = None


Step = Annotated[
    Union[GotoStep, DelayStep, ScrollStep, ClickStep],
    Field(discriminator="action"),
]


class ScenarioDocument(BaseModel):
    name: str
    description: str = ""
    start_url: str = ""
    steps: list[Step] = Field(default_factory=list)


class ScenarioInfo(BaseModel):
    name: str
    type: Literal["python", "json"]
    description: str = ""


class RunRequest(BaseModel):
    scenario: str
    loops: int = 1
    pause_between_loops_sec: float = 0.0
    headless: bool = False
    channel: str | None = "chrome"
    slow_mo: int = 0


class RunStatusResponse(BaseModel):
    state: str
    scenario: str | None = None
    loop: int = 0
    loops: int = 0
    error: str | None = None
