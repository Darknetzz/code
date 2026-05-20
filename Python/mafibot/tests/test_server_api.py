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


def test_websocket_rejects_bad_token(monkeypatch):
    monkeypatch.setenv("MAFIBOT_UI_TOKEN", "secret-token")
    try:
        with pytest.raises(Exception):
            with client.websocket_connect("/ws?token=wrong"):
                pass
    finally:
        monkeypatch.delenv("MAFIBOT_UI_TOKEN", raising=False)
