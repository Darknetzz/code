"""Gains ledger and lifetime merge."""

from __future__ import annotations

from pathlib import Path

import pytest

from mafibot.gains_ledger import (
    GainsLedger,
    load_lifetime_gains,
    merge_session_into_lifetime,
    save_lifetime_gains,
    source_for_crime_section,
)


def test_source_for_crime_section() -> None:
    assert source_for_crime_section("enkel") == "enkel_krim"
    assert source_for_crime_section("tung") == "tung_krim"
    assert source_for_crime_section("stjel") == "stjel"


def test_gains_ledger_record_and_merge() -> None:
    a = GainsLedger()
    a.record_action_event(
        action="crime",
        source="enkel_krim",
        success=True,
        money_delta=5000,
        rank_delta=2,
    )
    assert a.money_net == 5000
    assert a.money_by_source["enkel_krim"] == 5000
    assert a.rank_points_net == 2

    b = GainsLedger()
    b.record_money("stjel", -1000)
    a.merge(b)
    assert a.money_net == 4000
    assert a.money_by_source["stjel"] == -1000


def test_lifetime_persist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "mafibot"
    cfg.mkdir()
    monkeypatch.setattr(
        "mafibot.gains_ledger.get_config_dir",
        lambda: cfg,
    )
    session = GainsLedger()
    session.record_grams_sold(cannabis=10, opium=5)
    session.record_minion_skill("angrep", 0.5)
    merge_session_into_lifetime(session)
    loaded = load_lifetime_gains()
    assert loaded.cannabis_grams_sold == 10
    assert loaded.opium_grams_sold == 5
    assert loaded.minion_skills_net.get("angrep") == 0.5

    session2 = GainsLedger()
    session2.record_grams_sold(cannabis=3)
    merge_session_into_lifetime(session2)
    again = load_lifetime_gains()
    assert again.cannabis_grams_sold == 13

    save_lifetime_gains(GainsLedger())
    assert load_lifetime_gains().money_net == 0
