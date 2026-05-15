"""Unit tests for nested scenario planning (no Playwright)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from webbot.json_scenario import collect_expanded_plan_labels
from webbot.models import DelayStep, RunScenarioStep, ScenarioDocument


class TestExpandedPlan(unittest.TestCase):
    def test_skip_start_url_skips_implicit_goto(self) -> None:
        inner = ScenarioDocument(
            name="inner",
            start_url="https://inner.example",
            steps=[DelayStep(min=1, max=2)],
        )
        outer = ScenarioDocument(
            name="outer",
            steps=[
                RunScenarioStep(scenario="inner", skip_start_url=True),
            ],
        )
        docs = {"outer": outer, "inner": inner}

        def load(name: str) -> ScenarioDocument:
            return docs[name]

        with patch("webbot.json_scenario.load_json_scenario", load):
            labels = collect_expanded_plan_labels(
                outer,
                scenario_name="outer",
                stack=frozenset(),
                skip_implicit_start_url=False,
                label_prefix="",
                depth=0,
            )
        self.assertFalse(any("inner.example" in lab for lab in labels))

    def test_cycle_detected(self) -> None:
        a = ScenarioDocument(name="a", steps=[RunScenarioStep(scenario="b")])
        b = ScenarioDocument(name="b", steps=[RunScenarioStep(scenario="a")])
        docs = {"a": a, "b": b}

        def load(name: str) -> ScenarioDocument:
            return docs[name]

        with patch("webbot.json_scenario.load_json_scenario", load):
            with self.assertRaises(ValueError):
                collect_expanded_plan_labels(
                    a,
                    scenario_name="a",
                    stack=frozenset(),
                    skip_implicit_start_url=False,
                    label_prefix="",
                    depth=0,
                )


if __name__ == "__main__":
    unittest.main()
