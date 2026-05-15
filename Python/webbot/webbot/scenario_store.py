"""Load and save JSON scenarios from user config and built-in samples."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Literal

from webbot.browser import get_app_config_dir
from webbot.models import FlowGroup, GroupsDocument, GroupsResponse, ScenarioDocument

_BUILTIN_DIR = Path(__file__).parent / "builtin_scenarios"


def _legacy_groups_json_path() -> Path:
    """Old location: same folder as ``*.json`` flows, which made ``groups`` a false scenario."""
    return get_user_scenarios_dir() / "groups.json"


def _migrate_groups_file_if_needed() -> None:
    """Move ``scenarios/groups.json`` → ``<config>/groups.json`` once if needed."""
    new_path = get_app_config_dir() / "groups.json"
    old_path = _legacy_groups_json_path()
    if not old_path.exists():
        return
    if new_path.exists():
        old_path.unlink()
        return
    new_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old_path), str(new_path))


class ScenarioStoreConflict(ValueError):
    """Both ``name.json`` and ``name.py`` exist."""


def get_user_scenarios_dir() -> Path:
    path = get_app_config_dir() / "scenarios"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _seed_builtin_scenarios() -> None:
    _migrate_groups_file_if_needed()
    user_dir = get_user_scenarios_dir()
    if not _BUILTIN_DIR.exists():
        return
    for src in _BUILTIN_DIR.glob("*.json"):
        dest = user_dir / src.name
        if not dest.exists():
            shutil.copy2(src, dest)
    for src in _BUILTIN_DIR.glob("*.py"):
        dest = user_dir / src.name
        if not dest.exists():
            shutil.copy2(src, dest)


def list_json_scenario_names() -> list[str]:
    _seed_builtin_scenarios()
    user_dir = get_user_scenarios_dir()
    return sorted(p.stem for p in user_dir.glob("*.json"))


def json_scenario_path(name: str) -> Path:
    return get_user_scenarios_dir() / f"{name}.json"


def python_scenario_path(name: str) -> Path:
    return get_user_scenarios_dir() / f"{name}.py"


def list_python_scenario_names() -> list[str]:
    _seed_builtin_scenarios()
    user_dir = get_user_scenarios_dir()
    return sorted(p.stem for p in user_dir.glob("*.py"))


def scenario_kind(name: str) -> Literal["json", "python"] | None:
    """Which file backs this scenario stem. Raises if both ``.json`` and ``.py`` exist."""
    jp = json_scenario_path(name).exists()
    pp = python_scenario_path(name).exists()
    if jp and pp:
        raise ScenarioStoreConflict(
            f"Scenario '{name}' has both {name}.json and {name}.py — delete or rename one."
        )
    if jp:
        return "json"
    if pp:
        return "python"
    return None


def list_all_scenario_names() -> list[str]:
    return sorted(set(list_json_scenario_names()) | set(list_python_scenario_names()))


def load_python_source(name: str) -> str:
    path = python_scenario_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Python scenario not found: {name}")
    return path.read_text(encoding="utf-8")


def save_python_source(name: str, source: str) -> Path:
    if json_scenario_path(name).exists():
        raise ValueError(f"A JSON scenario '{name}.json' already exists — pick another name or delete it.")
    compile(source, f"<scenario {name}>", "exec")
    path = python_scenario_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8", newline="\n")
    return path


def delete_python_scenario(name: str) -> None:
    path = python_scenario_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Python scenario not found: {name}")
    path.unlink()


def load_json_scenario(name: str) -> ScenarioDocument:
    path = json_scenario_path(name)
    if not path.exists():
        raise FileNotFoundError(f"JSON scenario not found: {name}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "name" not in data:
        data = {**data, "name": name}
    doc = ScenarioDocument.model_validate(data)
    if doc.name != name:
        doc = doc.model_copy(update={"name": name})
    return doc


def save_json_scenario(doc: ScenarioDocument) -> Path:
    if python_scenario_path(doc.name).exists():
        raise ValueError(
            f"A Python scenario '{doc.name}.py' already exists — pick another name or delete it."
        )
    path = json_scenario_path(doc.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    return path


def delete_json_scenario(name: str) -> None:
    path = json_scenario_path(name)
    if not path.exists():
        raise FileNotFoundError(f"JSON scenario not found: {name}")
    path.unlink()


def rename_scenario_in_groups(old_name: str, new_name: str) -> None:
    """Replace ``old_name`` with ``new_name`` in every group's ``scenario_names``."""
    o = old_name.strip()
    n = new_name.strip()
    if not o or not n or o == n:
        return
    doc = load_groups_document()
    groups: list[FlowGroup] = []
    for g in doc.groups:
        names = [n if x == o else x for x in g.scenario_names]
        groups.append(FlowGroup(id=g.id, label=g.label, scenario_names=names))
    save_groups_document(GroupsDocument(groups=groups))


def finalize_scenario_rename(
    rename_from: str | None,
    new_stem: str,
    expected_kind: Literal["json", "python"],
) -> None:
    """After saving ``new_stem``, remove the old file if the flow was renamed; update group lists."""
    n = new_stem.strip()
    if not rename_from or not rename_from.strip() or not n:
        return
    old = rename_from.strip()
    if old == n:
        return
    try:
        k = scenario_kind(old)
    except ValueError:
        rename_scenario_in_groups(old, n)
        return
    if k == expected_kind:
        try:
            if k == "json":
                delete_json_scenario(old)
            else:
                delete_python_scenario(old)
        except FileNotFoundError:
            pass
    rename_scenario_in_groups(old, n)


def groups_json_path() -> Path:
    return get_app_config_dir() / "groups.json"


def load_groups_document() -> GroupsDocument:
    _migrate_groups_file_if_needed()
    path = groups_json_path()
    if not path.exists():
        return GroupsDocument(groups=[])
    data = json.loads(path.read_text(encoding="utf-8"))
    return GroupsDocument.model_validate(data)


def save_groups_document(doc: GroupsDocument) -> Path:
    _migrate_groups_file_if_needed()
    path = groups_json_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
    return path


def build_groups_response() -> GroupsResponse:
    """Resolve groups plus scenarios not assigned to any group."""
    seen: set[str] = set()
    doc = load_groups_document()
    groups: list[FlowGroup] = []
    for g in doc.groups:
        names = [n for n in g.scenario_names if n.strip()]
        groups.append(FlowGroup(id=g.id, label=g.label, scenario_names=names))
        seen.update(names)
    ungrouped = sorted(n for n in list_all_scenario_names() if n not in seen)
    return GroupsResponse(groups=groups, ungrouped=ungrouped)


def get_group_by_id(group_id: str) -> FlowGroup:
    doc = load_groups_document()
    for g in doc.groups:
        if g.id == group_id:
            return FlowGroup(id=g.id, label=g.label, scenario_names=list(g.scenario_names))
    raise KeyError(f"Unknown group: {group_id}")
