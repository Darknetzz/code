"""Scenario registry: JSON flows and user-editable Python ``.py`` files in the scenarios folder."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from playwright.async_api import Page

from webbot.json_scenario import make_json_runner
from webbot.models import ScenarioInfo
from webbot.python_scenario_loader import load_user_python_module, read_python_meta
from webbot.scenario_store import (
    list_all_scenario_names,
    list_json_scenario_names,
    python_scenario_path,
    scenario_kind,
)

ScenarioFn = Callable[[Page], Awaitable[None]]


def _python_list_description(name: str) -> str:
    path = python_scenario_path(name)
    try:
        mod = load_user_python_module(path, name)
        desc, labels = read_python_meta(mod)
        base = desc.strip() or f"Python scenario ({len(labels)} steps)" if labels else "Python scenario"
        return base
    except Exception:
        return "Python scenario (fix code to run)"


def list_scenarios() -> list[str]:
    return list_all_scenario_names()


def list_scenario_info() -> list[ScenarioInfo]:
    items: list[ScenarioInfo] = []
    for name in list_all_scenario_names():
        try:
            kind = scenario_kind(name)
        except Exception as exc:
            items.append(
                ScenarioInfo(name=name, type="json", description=f"Invalid: {exc}")
            )
            continue
        if kind == "json":
            from webbot.scenario_store import load_json_scenario

            try:
                doc = load_json_scenario(name)
                desc = doc.description or f"JSON scenario ({len(doc.steps)} steps)"
            except Exception:
                desc = "JSON scenario"
            items.append(ScenarioInfo(name=name, type="json", description=desc))
        elif kind == "python":
            items.append(
                ScenarioInfo(name=name, type="python", description=_python_list_description(name))
            )
    return sorted(items, key=lambda s: s.name)


def make_python_runner(name: str) -> ScenarioFn:
    path = python_scenario_path(name)

    async def _run(page: Page) -> None:
        mod = load_user_python_module(path, name)
        run_fn = __import__(
            "webbot.python_scenario_loader", fromlist=["get_python_run_fn"]
        ).get_python_run_fn(mod)
        await run_fn(page)

    return _run


def get_scenario(name: str) -> ScenarioFn:
    try:
        kind = scenario_kind(name)
    except Exception as exc:
        raise KeyError(str(exc)) from exc
    if kind is None:
        available = ", ".join(list_scenarios()) or "(none)"
        raise KeyError(f"Unknown scenario '{name}'. Available: {available}")
    if kind == "json":
        return make_json_runner(name)
    return make_python_runner(name)


def scenario_type(name: str) -> str:
    try:
        k = scenario_kind(name)
    except Exception as exc:
        raise KeyError(name) from exc
    if k is None:
        raise KeyError(name)
    return k
