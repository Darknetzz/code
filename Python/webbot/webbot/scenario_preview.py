"""Read-only scenario previews for the dashboard (JSON and Python)."""

from __future__ import annotations

from webbot.json_scenario import build_step_plan
from webbot.models import ScenarioPreview, ScenarioPreviewStep
from webbot.scenario_store import load_json_scenario
from webbot.scenarios import get_python_scenario_meta, scenario_type


def get_scenario_preview(name: str) -> ScenarioPreview:
    try:
        kind = scenario_type(name)
    except KeyError as exc:
        raise FileNotFoundError(f"Unknown scenario: {name}") from exc

    if kind == "python":
        meta = get_python_scenario_meta(name)
        steps = [
            ScenarioPreviewStep(index=index, label=label)
            for index, label in enumerate(meta.step_labels, start=1)
        ]
        return ScenarioPreview(
            name=name,
            type="python",
            description=meta.description,
            steps=steps,
            source=meta.source,
        )

    doc = load_json_scenario(name)
    steps = [
        ScenarioPreviewStep(index=index, label=label)
        for index, label in build_step_plan(doc)
    ]
    return ScenarioPreview(
        name=doc.name,
        type="json",
        description=doc.description,
        steps=steps,
        start_url=doc.start_url or None,
        random_delay_between_steps=doc.random_delay_between_steps,
        between_steps_min=doc.between_steps_min,
        between_steps_max=doc.between_steps_max,
        between_steps_distribution=doc.between_steps_distribution,
    )
