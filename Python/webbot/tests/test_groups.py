"""Tests for groups.json maintenance."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from webbot.models import FlowGroup, GroupsDocument
from webbot.scenario_store import remove_scenario_from_all_groups


class TestRemoveScenarioFromGroups(unittest.TestCase):
    def test_removes_matching_name_and_saves(self) -> None:
        doc_in = GroupsDocument(
            groups=[
                FlowGroup(
                    id="g1",
                    label="One",
                    scenario_names=["keep", "drop_me", ""],
                ),
                FlowGroup(
                    id="g2",
                    label="Two",
                    scenario_names=["drop_me"],
                ),
            ]
        )
        captured: dict[str, GroupsDocument] = {}

        def fake_load() -> GroupsDocument:
            return doc_in

        def fake_save(doc: GroupsDocument) -> None:
            captured["doc"] = doc

        with (
            patch("webbot.scenario_store.load_groups_document", side_effect=fake_load),
            patch("webbot.scenario_store.save_groups_document", side_effect=fake_save),
        ):
            remove_scenario_from_all_groups("drop_me")

        self.assertIn("doc", captured)
        out = captured["doc"]
        self.assertEqual(out.groups[0].scenario_names, ["keep", ""])
        self.assertEqual(out.groups[1].scenario_names, [])

    def test_no_save_when_absent(self) -> None:
        doc_in = GroupsDocument(
            groups=[FlowGroup(id="g1", label="One", scenario_names=["a", "b"])]
        )

        saved: list[GroupsDocument] = []

        def fake_load() -> GroupsDocument:
            return doc_in

        def fake_save(doc: GroupsDocument) -> None:
            saved.append(doc)

        with (
            patch("webbot.scenario_store.load_groups_document", side_effect=fake_load),
            patch("webbot.scenario_store.save_groups_document", side_effect=fake_save),
        ):
            remove_scenario_from_all_groups("missing")

        self.assertEqual(saved, [])
