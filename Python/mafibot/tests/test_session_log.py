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
    sl.end_session_log()
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


def test_per_session_log_lifecycle(log_dir: Path) -> None:
    path = sl.start_session_log("ranker", "2026-06-04 12:00:00")
    assert path.parent == log_dir / "sessions"
    assert path.is_file()
    assert sl.get_active_session_log_path() == path
    sl.log_session_event("ACTION", action="crime", ok=True, money_delta=100)
    sl.end_session_log()
    assert sl.get_active_session_log_path() is None
    lines = sl.read_log_lines(path, limit=20)
    assert any("SESSION" in line for line in lines)
    assert any("ACTION" in line and "crime" in line for line in lines)
    listed = sl.list_session_logs(limit=5)
    assert listed and listed[0].id == path.stem


def test_open_log_in_default_app(log_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []

    def fake_startfile(path: str) -> None:
        opened.append(path)

    monkeypatch.setattr(sl.sys, "platform", "win32")
    import os

    monkeypatch.setattr(os, "startfile", fake_startfile)
    path = sl.open_log_in_default_app()
    assert path.is_file()
    assert opened and Path(opened[0]) == path
