"""Registered automation scenarios (Python and JSON)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from playwright.async_api import Page

from webbot.json_scenario import make_json_runner
from webbot.models import ScenarioInfo
from webbot.scenario_store import list_json_scenario_names, load_json_scenario
from webbot.scenarios import example_site

ScenarioFn = Callable[[Page], Awaitable[None]]


@dataclass(frozen=True)
class PythonScenarioMeta:
    description: str
    step_labels: tuple[str, ...]
    source: str


_PYTHON_SCENARIOS: dict[str, tuple[ScenarioFn, PythonScenarioMeta]] = {
    "example": (
        example_site.run,
        PythonScenarioMeta(
            description="Browse example.com with human-like clicks (Python)",
            step_labels=example_site.STEP_LABELS,
            source="webbot/scenarios/example_site.py",
        ),
    ),
}


def get_python_scenario_meta(name: str) -> PythonScenarioMeta:
    if name not in _PYTHON_SCENARIOS:
        raise KeyError(name)
    return _PYTHON_SCENARIOS[name][1]


def list_scenarios() -> list[str]:
    return sorted(set(_PYTHON_SCENARIOS) | set(list_json_scenario_names()))


def list_scenario_info() -> list[ScenarioInfo]:
    items: list[ScenarioInfo] = []
    for name, (_, meta) in _PYTHON_SCENARIOS.items():
        n = len(meta.step_labels)
        desc = meta.description
        if n and "step" not in desc.lower():
            desc = f"{desc} ({n} steps)"
        items.append(ScenarioInfo(name=name, type="python", description=desc))
    for name in list_json_scenario_names():
        try:
            doc = load_json_scenario(name)
            desc = doc.description or f"JSON scenario ({len(doc.steps)} steps)"
        except Exception:
            desc = "JSON scenario"
        items.append(ScenarioInfo(name=name, type="json", description=desc))
    return sorted(items, key=lambda s: s.name)


def get_scenario(name: str) -> ScenarioFn:
    if name in _PYTHON_SCENARIOS:
        return _PYTHON_SCENARIOS[name][0]
    if name in list_json_scenario_names():
        return make_json_runner(name)
    available = ", ".join(list_scenarios()) or "(none)"
    raise KeyError(f"Unknown scenario '{name}'. Available: {available}")


def scenario_type(name: str) -> str:
    if name in _PYTHON_SCENARIOS:
        return "python"
    if name in list_json_scenario_names():
        return "json"
    raise KeyError(name)
