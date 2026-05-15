"""Registered JSON automation scenarios."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from playwright.async_api import Page

from webbot.json_scenario import make_json_runner
from webbot.models import ScenarioInfo
from webbot.scenario_store import list_json_scenario_names, load_json_scenario

ScenarioFn = Callable[[Page], Awaitable[None]]


def list_scenarios() -> list[str]:
    return list_json_scenario_names()


def list_scenario_info() -> list[ScenarioInfo]:
    items: list[ScenarioInfo] = []
    for name in list_json_scenario_names():
        try:
            doc = load_json_scenario(name)
            desc = doc.description or f"JSON scenario ({len(doc.steps)} steps)"
        except Exception:
            desc = "JSON scenario"
        items.append(ScenarioInfo(name=name, type="json", description=desc))
    return sorted(items, key=lambda s: s.name)


def get_scenario(name: str) -> ScenarioFn:
    if name not in list_json_scenario_names():
        available = ", ".join(list_scenarios()) or "(none)"
        raise KeyError(f"Unknown scenario '{name}'. Available: {available}")
    return make_json_runner(name)


def scenario_type(name: str) -> str:
    if name not in list_json_scenario_names():
        raise KeyError(name)
    return "json"
