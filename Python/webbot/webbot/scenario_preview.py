"""Read-only scenario previews for the dashboard (JSON flows)."""

from __future__ import annotations

from webbot.json_scenario import build_step_plan
from webbot.models import ScenarioPreview, ScenarioPreviewStep
from webbot.scenario_store import load_json_scenario


def get_scenario_preview(name: str) -> ScenarioPreview:
    try:
        doc = load_json_scenario(name)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Unknown scenario: {name}") from exc

    steps = [
        ScenarioPreviewStep(index=index, label=label) for index, label in build_step_plan(doc, root_name=name)
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
