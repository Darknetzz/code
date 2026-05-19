"""Report stream murder target tests."""

from __future__ import annotations

from mafibot.config import BotProfile
from mafibot.report_stream import pick_report_stream_target
from mafibot.state import ReportEntry
from mafibot.state_parsers import parse_report_stream


def test_parse_report_stream():
    text = "Rapportstream: BadGuy i Oslo NULL DELAY\nNoen skjøt på deg fra Evil i London"
    entries = parse_report_stream(text)
    assert any(e.null_delay for e in entries)
    assert any(e.incoming_shot for e in entries)


def test_retaliate_only_picks_shooter():
    profile = BotProfile(combat_enabled=True, murder_mode="retaliate_only")
    state = __import__("mafibot.state", fromlist=["GameState"]).GameState(
        report_entries=[
            ReportEntry(username="Shooter", city="London", incoming_shot=True),
            ReportEntry(username="Other", city="Oslo", null_delay=True),
        ]
    )
    pick = pick_report_stream_target(state, profile)
    assert pick is not None
    assert pick.username == "Shooter"
    assert pick.reason == "retaliate"
