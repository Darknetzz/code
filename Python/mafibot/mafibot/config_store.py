"""Load/save profiles and credentials for the dashboard."""

from __future__ import annotations

import json
import re
from pathlib import Path

from mafibot.config import (
    bundled_profiles_dir,
    get_config_dir,
    get_profiles_dir,
    load_bot_profile,
)
from mafibot.models import (
    BotProfileDocument,
    CredentialsStatus,
    CredentialsUpdate,
    ProfileListItem,
)


def _env_path() -> Path:
    return get_config_dir() / ".env"


_PROFILE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def validate_profile_name(name: str) -> str:
    stem = name.strip()
    if not stem or not _PROFILE_NAME_RE.match(stem):
        raise ValueError("Profile name must use letters, numbers, underscore, or hyphen only")
    return stem


def _bundled_names() -> set[str]:
    base = bundled_profiles_dir()
    if not base.is_dir():
        return set()
    return {p.stem for p in base.glob("*.json")}


def _user_names() -> set[str]:
    base = get_profiles_dir()
    if not base.is_dir():
        return set()
    return {p.stem for p in base.glob("*.json")}


def user_profile_path(name: str) -> Path:
    return get_profiles_dir() / f"{validate_profile_name(name)}.json"


def list_profile_names() -> list[str]:
    return [item.name for item in list_profiles_meta()]


def list_profiles_meta() -> list[ProfileListItem]:
    bundled = _bundled_names()
    user = _user_names()
    items: list[ProfileListItem] = []
    for name in sorted(bundled | user):
        in_bundled = name in bundled
        in_user = name in user
        items.append(
            ProfileListItem(
                name=name,
                is_bundled=in_bundled,
                has_user_copy=in_user,
                deletable=in_user,
            )
        )
    return items


def create_profile(name: str, *, copy_from: str | None = None) -> BotProfileDocument:
    stem = validate_profile_name(name)
    path = user_profile_path(stem)
    if path.is_file():
        raise ValueError(f"Profile already exists: {stem}")
    if copy_from:
        source = load_profile_document(copy_from.strip())
        data = source.model_dump()
        data["name"] = stem
        doc = BotProfileDocument.model_validate(data)
    else:
        doc = BotProfileDocument(name=stem)
    return save_profile_document(doc)


def delete_profile(name: str) -> None:
    stem = validate_profile_name(name)
    path = user_profile_path(stem)
    if not path.is_file():
        raise ValueError("Only custom or overridden profiles can be deleted")
    path.unlink()


def rename_profile(old_name: str, new_name: str) -> BotProfileDocument:
    old_stem = validate_profile_name(old_name)
    new_stem = validate_profile_name(new_name)
    if old_stem == new_stem:
        return load_profile_document(old_stem)
    new_path = user_profile_path(new_stem)
    if new_path.is_file():
        raise ValueError(f"Profile already exists: {new_stem}")
    doc = load_profile_document(old_stem)
    doc.name = new_stem
    saved = save_profile_document(doc)
    old_user = user_profile_path(old_stem)
    if old_user.is_file() and old_stem != new_stem:
        old_user.unlink()
    return saved


def load_profile_document(name: str) -> BotProfileDocument:
    profile = load_bot_profile(name)
    return BotProfileDocument.model_validate(profile.model_dump())


def save_profile_document(doc: BotProfileDocument) -> BotProfileDocument:
    stem = validate_profile_name(doc.name)
    dest = get_profiles_dir()
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{stem}.json"
    data = doc.model_dump()
    data["name"] = stem
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return BotProfileDocument.model_validate(data)


def get_credentials_status() -> CredentialsStatus:
    path = _env_path()
    has_user = False
    has_password = False
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        has_user = bool(re.search(r"^MAFIA_USER=\S", text, re.M))
        has_password = bool(re.search(r"^MAFIA_PASS=\S", text, re.M))
    return CredentialsStatus(
        has_user=has_user,
        has_password=has_password,
        env_path=str(path),
    )


def _read_env_pairs() -> dict[str, str]:
    path = _env_path()
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, val = line.partition("=")
            out[key.strip()] = val.strip()
    return out


def save_credentials(update: CredentialsUpdate) -> CredentialsStatus:
    get_config_dir().mkdir(parents=True, exist_ok=True)
    pairs = _read_env_pairs()
    if update.user.strip():
        pairs["MAFIA_USER"] = update.user.strip()
    if update.password:
        pairs["MAFIA_PASS"] = update.password
    lines = [f"{k}={v}" for k, v in sorted(pairs.items()) if k in ("MAFIA_USER", "MAFIA_PASS")]
    content = "\n".join(lines) + ("\n" if lines else "")
    _env_path().write_text(content, encoding="utf-8")
    return get_credentials_status()
