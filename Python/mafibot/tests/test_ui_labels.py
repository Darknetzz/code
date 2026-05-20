"""ACTION_DISPLAY_LABELS stays aligned with GAME_TABS and app.js ACTION_CATALOG."""

from __future__ import annotations

import re
from pathlib import Path

from mafibot.selectors import ACTION_DISPLAY_LABELS, GAME_TABS, action_display_label

APP_JS = Path(__file__).resolve().parents[1] / "mafibot" / "static" / "app.js"

# Sidebar-only actions (not top tabs)
_SIDEBAR_DISPLAY = frozenset({"business", "ship", "drugs", "murder", "bank"})


def test_action_display_labels_cover_catalog_ids():
    text = APP_JS.read_text(encoding="utf-8")
    ids = re.findall(r'\bid:\s*"([a-z_]+)"', text.split("const ACTION_CATALOG")[1].split("];")[0])
    assert ids, "could not parse ACTION_CATALOG ids from app.js"
    for action_id in ids:
        assert action_id in ACTION_DISPLAY_LABELS, action_id


def test_app_js_labels_match_python():
    text = APP_JS.read_text(encoding="utf-8")
    block = text.split("const ACTION_CATALOG")[1].split("];")[0]
    pairs = re.findall(r'id:\s*"([^"]+)"\s*,\s*label:\s*"([^"]+)"', block)
    assert pairs
    for action_id, label in pairs:
        assert ACTION_DISPLAY_LABELS[action_id] == label, action_id


def test_tab_actions_use_game_tabs():
    for action_id, label in ACTION_DISPLAY_LABELS.items():
        if action_id in _SIDEBAR_DISPLAY:
            continue
        if action_id == "bank":
            assert label == "Bank"
            continue
        assert label == GAME_TABS[action_id], action_id


def test_action_display_label_helper():
    assert action_display_label("crime") == "Kriminalitet"
    assert action_display_label("unknown_action") == "unknown_action"
