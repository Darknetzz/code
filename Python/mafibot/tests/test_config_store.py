"""Profile and credentials persistence."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mafibot.config_store import (
    get_credentials_status,
    list_profile_names,
    load_profile_document,
    save_credentials,
    save_profile_document,
)
from mafibot.models import BotProfileDocument, CredentialsUpdate


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    cfg = tmp_path / "mafibot"
    prof = cfg / "profiles"
    prof.mkdir(parents=True)
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with patch("mafibot.config_store.get_config_dir", return_value=cfg), patch(
        "mafibot.config_store.get_profiles_dir", return_value=prof
    ), patch("mafibot.config.get_config_dir", return_value=cfg), patch(
        "mafibot.config.get_profiles_dir", return_value=prof
    ):
        yield cfg, prof


def test_profile_round_trip(isolated_config):
    _cfg, prof = isolated_config
    doc = BotProfileDocument(name="custom", build="okonom", stay_in_hotel=False)
    saved = save_profile_document(doc)
    assert saved.name == "custom"
    path = prof / "custom.json"
    assert path.is_file()
    loaded = load_profile_document("custom")
    assert loaded.build == "okonom"
    assert loaded.stay_in_hotel is False


def test_list_profiles_includes_bundled():
    names = list_profile_names()
    assert "ranker" in names


def test_credentials_write(isolated_config):
    cfg, _ = isolated_config
    st = save_credentials(CredentialsUpdate(user="alice", password="secret"))
    assert st.has_user
    assert st.has_password
    env = cfg / ".env"
    assert env.is_file()
    text = env.read_text(encoding="utf-8")
    assert "MAFIA_USER=alice" in text
    assert "MAFIA_PASS=secret" in text
    st2 = get_credentials_status()
    assert st2.has_user and st2.has_password


def test_credentials_merge_password_only(isolated_config):
    cfg, _ = isolated_config
    save_credentials(CredentialsUpdate(user="bob", password="p1"))
    save_credentials(CredentialsUpdate(user="", password="p2"))
    text = (cfg / ".env").read_text(encoding="utf-8")
    assert "MAFIA_USER=bob" in text
    assert "MAFIA_PASS=p2" in text
