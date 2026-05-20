"""Session log file persistence."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from mafibot import session_log as sl


@pytest.fixture
def log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cfg = tmp_path / "mafibot"
    cfg.mkdir()
    monkeypatch.setattr(sl, "get_config_dir", lambda: cfg)
    monkeypatch.setattr(sl, "_configured", False)
    return cfg / "logs"


def test_configure_and_read_tail(log_dir: Path) -> None:
    path = sl.configure_session_file_logging()
    assert path == log_dir / "mafibot.log"
    logging.getLogger("mafibot").info("hello from test")
    lines = sl.read_recent_log_lines(limit=10)
    assert any("hello from test" in line for line in lines)


def test_append_ui_log_line(log_dir: Path) -> None:
    sl.append_ui_log_line("Profile saved")
    lines = sl.read_recent_log_lines()
    assert any("UI: Profile saved" in line for line in lines)


def test_clear_session_log(log_dir: Path) -> None:
    sl.append_ui_log_line("line one")
    sl.clear_session_log()
    assert sl.read_recent_log_lines() == []
