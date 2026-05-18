"""FastAPI smoke tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from mafibot.server import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "config_dir" in data


def test_profiles_list():
    r = client.get("/api/profiles")
    assert r.status_code == 200
    assert "ranker" in r.json()


def test_get_profile_ranker():
    r = client.get("/api/profiles/ranker")
    assert r.status_code == 200
    assert r.json()["name"] == "ranker"


def test_run_requires_tos():
    r = client.post("/api/run", json={"profile": "ranker", "accept_tos": False})
    assert r.status_code == 400
