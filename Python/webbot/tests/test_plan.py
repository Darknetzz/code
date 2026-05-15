"""Unit tests for nested scenario planning (no Playwright)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from webbot.json_scenario import collect_expanded_plan_labels
from webbot.models import ClickStep, DelayStep, ExitStep, IfPresentStep, RunScenarioStep, ScenarioDocument


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

        def kind(name: str) -> str | None:
            return "json" if name in docs else None

        with patch("webbot.json_scenario.load_json_scenario", load), patch(
            "webbot.json_scenario.scenario_kind", kind
        ):
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

        def kind(name: str) -> str | None:
            return "json" if name in docs else None

        with patch("webbot.json_scenario.load_json_scenario", load), patch(
            "webbot.json_scenario.scenario_kind", kind
        ):
            with self.assertRaises(ValueError):
                collect_expanded_plan_labels(
                    a,
                    scenario_name="a",
                    stack=frozenset(),
                    skip_implicit_start_url=False,
                    label_prefix="",
                    depth=0,
                )

    def test_if_present_plan_order(self) -> None:
        doc = ScenarioDocument(
            name="branchy",
            steps=[
                IfPresentStep(
                    by="role",
                    role="button",
                    name="OK",
                    timeout_ms=500,
                    then_steps=[ClickStep(by="role", role="link", name="A")],
                    else_steps=[ExitStep(message="nope")],
                )
            ],
        )
        labels = collect_expanded_plan_labels(
            doc,
            scenario_name="branchy",
            stack=frozenset(),
            skip_implicit_start_url=False,
            label_prefix="",
            depth=0,
        )
        self.assertGreaterEqual(len(labels), 3)
        self.assertTrue(labels[0].startswith("if_present"))
        self.assertIn("[if › then]", labels[1])
        self.assertIn("[if › else]", labels[2])


if __name__ == "__main__":
    unittest.main()
