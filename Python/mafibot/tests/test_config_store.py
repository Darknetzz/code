"""Profile and credentials persistence."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mafibot.config_store import (
    create_profile,
    delete_profile,
    get_credentials_status,
    list_profile_names,
    list_profiles_meta,
    load_profile_document,
    rename_profile,
    save_credentials,
    save_profile_document,
    user_profile_path,
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


def test_create_and_delete_profile(isolated_config):
    _cfg, prof = isolated_config
    doc = create_profile("mine", copy_from="ranker")
    assert doc.name == "mine"
    assert user_profile_path("mine").is_file()
    meta = {m.name: m for m in list_profiles_meta()}
    assert meta["mine"].deletable and not meta["mine"].is_bundled
    delete_profile("mine")
    assert not user_profile_path("mine").is_file()


def test_rename_profile(isolated_config):
    create_profile("old", copy_from=None)
    renamed = rename_profile("old", "new")
    assert renamed.name == "new"
    assert user_profile_path("new").is_file()
    assert not user_profile_path("old").is_file()


def test_delete_bundled_without_copy_fails(isolated_config):
    import pytest

    with pytest.raises(ValueError, match="delete"):
        delete_profile("ranker")


def test_save_strips_legacy_crime_fields(isolated_config):
    _cfg, prof = isolated_config
    doc = BotProfileDocument(
        name="crimey",
        crime_actions=["enkel"],
        crime_kind="perform",
        crime_perform_type="any",
    )
    save_profile_document(doc)
    raw = (prof / "crimey.json").read_text(encoding="utf-8")
    assert "crime_kind" not in raw
    assert "crime_actions" in raw
    loaded = load_profile_document("crimey")
    assert loaded.crime_actions == ["enkel"]


def test_credentials_merge_password_only(isolated_config):
    cfg, _ = isolated_config
    save_credentials(CredentialsUpdate(user="bob", password="p1"))
    save_credentials(CredentialsUpdate(user="", password="p2"))
    text = (cfg / ".env").read_text(encoding="utf-8")
    assert "MAFIA_USER=bob" in text
    assert "MAFIA_PASS=p2" in text
