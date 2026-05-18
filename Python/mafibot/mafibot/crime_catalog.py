"""Kriminalitet tab — sections and option labels from mafiaspillet.no (2026)."""

from __future__ import annotations

from dataclasses import dataclass

from mafibot.config import BotProfile

CRIME_SECTIONS: tuple[str, ...] = ("enkel", "tung", "stjel")


@dataclass(frozen=True)
class CrimeOption:
    id: str
    label: str
    patterns: tuple[str, ...]


@dataclass(frozen=True)
class CrimeSection:
    id: str
    title: str
    submit_labels: tuple[str, ...]
    options: tuple[CrimeOption, ...]


ENKEL_SECTION = CrimeSection(
    id="enkel",
    title="Enkel kriminalitet",
    submit_labels=("utfør",),
    options=(
        CrimeOption(
            "automat",
            "Bryt opp en spilleautomat",
            ("spilleautomat", "bryt opp"),
        ),
        CrimeOption("kiosk", "Ran en kiosk", ("kiosk",)),
        # Legacy / rank-gated crimes still seen on some accounts
        CrimeOption(
            "gate",
            "Ran tilfeldig person på gata",
            ("tilfeldig person", "ran tilfeldig", "person på gata"),
        ),
        CrimeOption("butikk", "Nask fra en butikk", ("nask", "butikk")),
    ),
)

TUNG_SECTION = CrimeSection(
    id="tung",
    title="Tung kriminalitet",
    submit_labels=("utfør",),
    options=(
        CrimeOption("pengetransport", "Ran en pengetransport", ("pengetransport",)),
        CrimeOption("bensin", "Ran en bensinstasjon", ("bensinstasjon", "bensin")),
    ),
)

STJEL_SECTION = CrimeSection(
    id="stjel",
    title="Stjel",
    submit_labels=("stjel",),
    options=(
        CrimeOption("garasje", "Stjel fra garasjen", ("garasje",)),
        CrimeOption("vapen", "Stjel fra våpenlageret", ("våpenlager", "våpen")),
        CrimeOption("penger", "Stjel penger", ("stjel penger", "penger")),
    ),
)

SECTIONS: dict[str, CrimeSection] = {
    "enkel": ENKEL_SECTION,
    "tung": TUNG_SECTION,
    "stjel": STJEL_SECTION,
}

_action_index = 0
_choice_index: dict[str, int] = {}


def reset_indices() -> None:
    global _action_index
    _action_index = 0
    _choice_index.clear()


def _legacy_crime_actions(profile: BotProfile) -> list[str]:
    if profile.crime_actions:
        return [a for a in profile.crime_actions if a in SECTIONS]
    if profile.crime_kind == "steal":
        return ["stjel"]
    if profile.crime_kind == "perform":
        if profile.crime_perform_type == "tung":
            return ["tung"]
        if profile.crime_perform_type == "lett":
            return ["enkel"]
        return ["enkel", "tung"]
    return ["enkel"]


def crime_actions_enabled(profile: BotProfile) -> list[str]:
    enabled = [a for a in _legacy_crime_actions(profile) if a in SECTIONS]
    return enabled or ["enkel"]


def _choices_for_section(profile: BotProfile, section_id: str) -> list[str]:
    field = {
        "enkel": "crime_enkel_choices",
        "tung": "crime_tung_choices",
        "stjel": "crime_steal_items",
    }.get(section_id)
    if not field:
        return []
    raw = getattr(profile, field, None) or []
    if section_id == "stjel" and not raw and profile.crime_steal_what:
        what = profile.crime_steal_what.strip().lower()
        for opt in STJEL_SECTION.options:
            if what in opt.id or any(what in p for p in opt.patterns):
                return [opt.id]
        return [what] if what else []
    return [c.strip() for c in raw if c and str(c).strip()]


def pick_crime_section(profile: BotProfile) -> str:
    """Next section to run (enkel / tung / stjel), with rotation when enabled."""
    global _action_index
    actions = crime_actions_enabled(profile)
    if profile.crime_rotate_actions and len(actions) > 1:
        section = actions[_action_index % len(actions)]
        _action_index += 1
        return section
    return actions[0]


def pick_option_ids(profile: BotProfile, section_id: str) -> list[str]:
    """Option id(s) to try this run; empty configured list = any option in section."""
    configured = _choices_for_section(profile, section_id)
    section = SECTIONS[section_id]
    valid = {o.id for o in section.options}
    configured = [c for c in configured if c in valid]
    if not configured:
        return [o.id for o in section.options]
    if profile.crime_rotate_actions and len(configured) > 1:
        idx = _choice_index.get(section_id, 0)
        chosen = configured[idx % len(configured)]
        _choice_index[section_id] = idx + 1
        return [chosen]
    return configured


def option_match_labels(section_id: str, option_id: str) -> tuple[str, ...]:
    section = SECTIONS[section_id]
    for opt in section.options:
        if opt.id == option_id:
            return (opt.label, *opt.patterns)
    return (option_id,)


def section_submit_labels(section_id: str) -> tuple[str, ...]:
    return SECTIONS[section_id].submit_labels
