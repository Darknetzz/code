"""Social actions use paced clicks."""

from __future__ import annotations

import inspect

from mafibot.actions import social


def test_messages_action_uses_human_click_paced():
    source = inspect.getsource(social.MessagesAction.run)
    assert "human_click_paced" in source
    assert "from webbot.human import human_click" not in source
