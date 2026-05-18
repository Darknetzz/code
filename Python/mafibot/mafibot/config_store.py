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
from mafibot.models import BotProfileDocument, CredentialsStatus, CredentialsUpdate


def _env_path() -> Path:
    return get_config_dir() / ".env"


def list_profile_names() -> list[str]:
    names: set[str] = set()
    for base in (bundled_profiles_dir(), get_profiles_dir()):
        if not base.is_dir():
            continue
        for p in base.glob("*.json"):
            names.add(p.stem)
    return sorted(names)


def load_profile_document(name: str) -> BotProfileDocument:
    profile = load_bot_profile(name)
    return BotProfileDocument.model_validate(profile.model_dump())


def save_profile_document(doc: BotProfileDocument) -> BotProfileDocument:
    stem = doc.name.strip()
    if not stem or not re.match(r"^[a-zA-Z0-9_-]+$", stem):
        raise ValueError("Invalid profile name")
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
