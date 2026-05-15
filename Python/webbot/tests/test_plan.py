"""Unit tests for nested scenario planning (no Playwright)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from webbot.json_scenario import collect_expanded_plan_labels, document_has_explicit_open_url, validate_workflow_jump_constraints
from webbot.models import (
    ClickStep,
    DelayStep,
    ExitStep,
    IfPresentStep,
    OpenUrlStep,
    RunScenarioStep,
    ScenarioDocument,
    WorkflowGotoStep,
)


class TestLegacyGotoMigration(unittest.TestCase):
    def test_legacy_goto_url_becomes_open_url(self) -> None:
        doc = ScenarioDocument.model_validate(
            {
                "name": "m",
                "steps": [{"action": "goto", "url": "https://legacy.example"}],
            }
        )
        self.assertIsInstance(doc.steps[0], OpenUrlStep)
        self.assertEqual(doc.steps[0].url, "https://legacy.example")

    def test_workflow_goto_with_label_preserved(self) -> None:
        doc = ScenarioDocument.model_validate(
            {
                "name": "m",
                "steps": [{"action": "goto", "goto_label": "here", "url": "https://ignored.example"}],
            }
        )
        self.assertIsInstance(doc.steps[0], WorkflowGotoStep)
        self.assertEqual(doc.steps[0].goto_label, "here")


class TestWorkflowGotoValidation(unittest.TestCase):
    def test_document_has_explicit_open_url(self) -> None:
        doc = ScenarioDocument(name="x", steps=[OpenUrlStep(url="https://a")])
        self.assertTrue(document_has_explicit_open_url(doc.steps))

    def test_validate_forward_goto(self) -> None:
        doc = ScenarioDocument(
            name="x",
            steps=[
                DelayStep(),
                WorkflowGotoStep(goto_label="end"),
                OpenUrlStep(url="https://x", workflow_label="end"),
            ],
        )
        validate_workflow_jump_constraints(doc)

    def test_duplicate_workflow_label_rejected(self) -> None:
        doc = ScenarioDocument(
            name="x",
            steps=[
                OpenUrlStep(url="https://a", workflow_label="dup"),
                OpenUrlStep(url="https://b", workflow_label="dup"),
            ],
        )
        with self.assertRaises(ValueError):
            validate_workflow_jump_constraints(doc)

    def test_backward_goto_rejected(self) -> None:
        doc = ScenarioDocument(
            name="x",
            steps=[
                OpenUrlStep(url="https://a", workflow_label="first"),
                WorkflowGotoStep(goto_label="first"),
            ],
        )
        with self.assertRaises(ValueError):
            validate_workflow_jump_constraints(doc)


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
