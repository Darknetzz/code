"""Registered automation scenarios."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from playwright.async_api import Page

from webbot.scenarios import example_site

ScenarioFn = Callable[[Page], Awaitable[None]]

SCENARIOS: dict[str, ScenarioFn] = {
    "example": example_site.run,
}


def list_scenarios() -> list[str]:
    return sorted(SCENARIOS.keys())


def get_scenario(name: str) -> ScenarioFn:
    try:
        return SCENARIOS[name]
    except KeyError as exc:
        available = ", ".join(list_scenarios()) or "(none)"
        raise KeyError(f"Unknown scenario '{name}'. Available: {available}") from exc
