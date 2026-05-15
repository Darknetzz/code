"""Scenario previews for JSON (expanded steps) and Python (STEP_LABELS)."""

from __future__ import annotations

from webbot.json_scenario import build_step_plan
from webbot.models import ScenarioPreview, ScenarioPreviewStep
from webbot.python_scenario_loader import load_user_python_module, read_python_meta
from webbot.scenario_store import (
    ScenarioStoreConflict,
    load_json_scenario,
    python_scenario_path,
    scenario_kind,
)


def get_scenario_preview(name: str) -> ScenarioPreview:
    try:
        kind = scenario_kind(name)
    except ScenarioStoreConflict as exc:
        raise FileNotFoundError(str(exc)) from exc

    if kind is None:
        raise FileNotFoundError(f"Unknown scenario: {name}")

    if kind == "json":
        doc = load_json_scenario(name)
        steps = [
            ScenarioPreviewStep(index=index, label=label)
            for index, label in build_step_plan(doc, root_name=name)
        ]
        return ScenarioPreview(
            name=doc.name,
            type="json",
            description=doc.description,
            steps=steps,
            source=None,
            start_url=doc.start_url or None,
            random_delay_between_steps=doc.random_delay_between_steps,
            between_steps_min=doc.between_steps_min,
            between_steps_max=doc.between_steps_max,
            between_steps_distribution=doc.between_steps_distribution,
        )

    path = python_scenario_path(name)
    try:
        mod = load_user_python_module(path, name)
        desc, labels = read_python_meta(mod)
    except Exception as exc:
        desc = f"(load error) {exc}"
        labels = ()

    steps = [
        ScenarioPreviewStep(index=i, label=lab)
        for i, lab in enumerate(labels, start=1)
    ]
    if not steps:
        steps = [ScenarioPreviewStep(index=1, label=f"Python scenario — define STEP_LABELS for a step list")]
    return ScenarioPreview(
        name=name,
        type="python",
        description=desc.strip() or "Python scenario",
        steps=steps,
        source=str(path),
        start_url=None,
        random_delay_between_steps=False,
        between_steps_min=0.3,
        between_steps_max=1.2,
        between_steps_distribution="triangular",
    )
