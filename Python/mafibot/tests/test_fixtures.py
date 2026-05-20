from pathlib import Path

import pytest

from mafibot.fixtures import promote_discovery_fixtures, verification_summary
from mafibot.verify_pages import ACTION_PAGES


def test_verification_summary_empty(tmp_path, monkeypatch):
    from mafibot import fixtures as fx

    monkeypatch.setattr(fx, "find_latest_discovery_run", lambda _base=None: None)
    summary = verification_summary()
    assert summary.run_dir is None
    assert not summary.ok


def test_promote_discovery_fixtures(tmp_path):
    run = tmp_path / "20260101_120000"
    run.mkdir()
    for logical in ACTION_PAGES:
        (run / f"{logical}.html").write_text(
            f"<html><body>{logical} test</body></html>",
            encoding="utf-8",
        )
    dest = tmp_path / "fixtures"
    out, copied = promote_discovery_fixtures(run, dest=dest)
    assert out == dest
    assert len(copied) == len(ACTION_PAGES)
    assert (dest / "crime.html").is_file()
