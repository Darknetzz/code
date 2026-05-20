"""FastAPI smoke tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mafibot.server import app

client = TestClient(app, raise_server_exceptions=False)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "config_dir" in data


def test_profiles_list():
    r = client.get("/api/profiles")
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "ranker" in names


def test_get_profile_ranker():
    r = client.get("/api/profiles/ranker")
    assert r.status_code == 200
    assert r.json()["name"] == "ranker"


def test_run_requires_tos():
    r = client.post("/api/run", json={"profile": "ranker", "accept_tos": False})
    assert r.status_code == 400


def test_open_log_file():
    r = client.post("/api/logs/open")
    assert r.status_code == 200
    assert r.json().get("ok") is True
    assert "mafibot.log" in r.json().get("path", "")


def test_preflight_endpoint():
    r = client.get("/api/preflight")
    assert r.status_code == 200
    data = r.json()
    assert "ok" in data
    assert "checks" in data


def test_api_requires_token_when_set(monkeypatch):
    monkeypatch.setenv("MAFIBOT_UI_TOKEN", "secret-token")
    try:
        r = client.get("/api/health")
        assert r.status_code == 401
        r2 = client.get("/api/health", headers={"X-Mafibot-Token": "secret-token"})
        assert r2.status_code == 200
    finally:
        monkeypatch.delenv("MAFIBOT_UI_TOKEN", raising=False)


def test_session_metrics_with_saved_summary(tmp_path, monkeypatch):
    from mafibot import session_metrics as sm

    cfg = tmp_path / "mafibot"
    cfg.mkdir()
    monkeypatch.setattr(sm, "get_config_dir", lambda: cfg)
    sm.save_last_session_summary(
        sm.SessionMetrics(
            profile="ranker",
            started_at="2026-05-20T10:00:00",
            ended_at="2026-05-20T11:00:00",
            actions_run=3,
            samples_in_hotel=10,
            samples_out_hotel=2,
            rank_start=100_000,
            rank_end=100_500,
            action_counts={"crime": 12, "missions": 4},
        )
    )
    r = client.get("/api/session/metrics")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["profile"] == "ranker"
    assert data["hotel_time_percent"] is not None
    assert data["rank_points_gained"] == 500
    assert data["action_counts"]["crime"] == 12


def test_websocket_rejects_bad_token(monkeypatch):
    monkeypatch.setenv("MAFIBOT_UI_TOKEN", "secret-token")
    try:
        with pytest.raises(Exception):
            with client.websocket_connect("/ws?token=wrong"):
                pass
    finally:
        monkeypatch.delenv("MAFIBOT_UI_TOKEN", raising=False)
