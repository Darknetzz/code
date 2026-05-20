from pathlib import Path

from mafibot.config import BotProfile
from mafibot.minions_page import (
    MinionInfo,
    MinionsRoster,
    parse_minions_from_html,
    resolve_minion_training,
)

_FIXTURE = (
    Path(__file__).resolve().parent / "fixtures/discovered/minions_folk.html"
)


def test_parse_minions_from_fixture():
    html = _FIXTURE.read_text(encoding="utf-8")
    roster = parse_minions_from_html(html)
    assert roster.total == 11
    assert roster.alive_count == 4
    assert roster.dead_count == 7
    alive = [m for m in roster.minions if m.alive]
    assert [m.name for m in alive] == [
        "Hozoxube",
        "Bofilyci",
        "Rapuvihu",
        "Mahycuzo",
    ]
    hoz = next(m for m in roster.minions if m.name == "Hozoxube")
    assert hoz.id == "38633"
    assert hoz.training == "angrep"
    dead = next(m for m in roster.minions if m.name == "Pigapuwy")
    assert not dead.alive
    assert dead.id == "14136"


def test_resolve_minion_training_uses_profile_map():
    profile = BotProfile(
        name="t",
        minions_training={"Mahycuzo": "intelligens"},
        minions_default_training="beskyttelse",
    )
    m = MinionInfo(id="1", name="Mahycuzo", alive=True, training="angrep")
    assert resolve_minion_training(profile, m) == "intelligens"
    other = MinionInfo(id="2", name="Newguy", alive=True)
    assert resolve_minion_training(profile, other) == "beskyttelse"
    dead = MinionInfo(id="3", name="Dead", alive=False)
    assert resolve_minion_training(profile, dead) is None


def test_parse_empty_without_table():
    assert parse_minions_from_html("<html></html>").total == 0
