"""Load and save JSON scenarios from user config and built-in samples."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from webbot.browser import get_app_config_dir
from webbot.models import ScenarioDocument

_BUILTIN_DIR = Path(__file__).parent / "builtin_scenarios"


def get_user_scenarios_dir() -> Path:
    path = get_app_config_dir() / "scenarios"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _seed_builtin_scenarios() -> None:
    user_dir = get_user_scenarios_dir()
    if not _BUILTIN_DIR.exists():
        return
    for src in _BUILTIN_DIR.glob("*.json"):
        dest = user_dir / src.name
        if not dest.exists():
            shutil.copy2(src, dest)


def list_json_scenario_names() -> list[str]:
    _seed_builtin_scenarios()
    user_dir = get_user_scenarios_dir()
    return sorted(p.stem for p in user_dir.glob("*.json"))


def json_scenario_path(name: str) -> Path:
    return get_user_scenarios_dir() / f"{name}.json"


def load_json_scenario(name: str) -> ScenarioDocument:
    path = json_scenario_path(name)
    if not path.exists():
        raise FileNotFoundError(f"JSON scenario not found: {name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    doc = ScenarioDocument.model_validate(data)
    if doc.name != name:
        doc = doc.model_copy(update={"name": name})
    return doc


def save_json_scenario(doc: ScenarioDocument) -> Path:
    path = json_scenario_path(doc.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    return path


def delete_json_scenario(name: str) -> None:
    path = json_scenario_path(name)
    if not path.exists():
        raise FileNotFoundError(f"JSON scenario not found: {name}")
    path.unlink()
