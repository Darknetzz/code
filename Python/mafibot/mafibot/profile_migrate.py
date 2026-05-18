"""Migrate legacy crime profile fields to crime_actions / section choices."""

from __future__ import annotations

from mafibot.crime_catalog import SECTIONS, STJEL_SECTION

LEGACY_CRIME_KEYS = (
    "crime_kind",
    "crime_perform_type",
    "crime_steal_what",
)


def migrate_crime_fields(data: dict) -> dict:
    """Return a copy with crime_actions populated from legacy fields when needed."""
    out = dict(data)
    actions = [a for a in (out.get("crime_actions") or []) if a in SECTIONS]
    if actions:
        out["crime_actions"] = actions
        return out

    kind = out.get("crime_kind")
    perform = out.get("crime_perform_type")
    if kind == "steal":
        actions = ["stjel"]
    elif kind == "perform":
        if perform == "tung":
            actions = ["tung"]
        elif perform == "lett":
            actions = ["enkel"]
        else:
            actions = ["enkel", "tung"]
    else:
        actions = ["enkel"]

    out["crime_actions"] = actions

    steal_what = (out.get("crime_steal_what") or "").strip().lower()
    if steal_what and not out.get("crime_steal_items"):
        for opt in STJEL_SECTION.options:
            if steal_what in opt.id or any(steal_what in p for p in opt.patterns):
                out["crime_steal_items"] = [opt.id]
                break
        else:
            if steal_what in {o.id for o in STJEL_SECTION.options}:
                out["crime_steal_items"] = [steal_what]

    return out


def strip_legacy_crime_keys(data: dict) -> dict:
    """Remove deprecated crime keys from persisted profile JSON."""
    out = migrate_crime_fields(data)
    for key in LEGACY_CRIME_KEYS:
        out.pop(key, None)
    return out
