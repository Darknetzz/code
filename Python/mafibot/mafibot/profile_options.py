"""Resolve per-action settings from BotProfile."""

from __future__ import annotations

from mafibot.config import BotProfile
from mafibot.crime_catalog import crime_actions_enabled


def messages_interval_minutes(profile: BotProfile) -> int:
    return profile.messages_interval_minutes or profile.social_interval_minutes


def family_interval_minutes(profile: BotProfile) -> int:
    return profile.family_interval_minutes or profile.social_interval_minutes


def hospital_enabled(profile: BotProfile) -> bool:
    return "hospital" in profile.economy_order


def hospital_health_threshold(profile: BotProfile) -> int:
    return profile.hospital_health_threshold


def needs_hospital_visit(profile: BotProfile, state) -> bool:
    if state.health_percent is None:
        return False
    if state.health_percent >= 100:
        return False
    return state.health_percent < hospital_health_threshold(profile)


def crime_min_health_percent(profile: BotProfile) -> int:
    if profile.crime_min_health_percent is not None:
        return profile.crime_min_health_percent
    return profile.min_health_percent


def crime_steal_enabled(profile: BotProfile) -> bool:
    return "stjel" in crime_actions_enabled(profile)


def crime_steal_target_mode(profile: BotProfile) -> str:
    return profile.crime_steal_target_mode


def crime_steal_username(profile: BotProfile) -> str:
    return profile.crime_steal_username.strip()


def crime_submit_labels(profile: BotProfile) -> tuple[str, ...]:
    labels = [lb.strip() for lb in profile.crime_button_labels if lb.strip()]
    if labels:
        return tuple(labels)
    return ("utfør", "stjel", "begå", "gjør", "bekreft", "ok")


def crime_needs_steal_username(profile: BotProfile) -> bool:
    return (
        crime_steal_enabled(profile)
        and crime_steal_target_mode(profile) == "specific"
        and not crime_steal_username(profile)
    )


def crime_any_section_ready(profile: BotProfile, state) -> bool:
    if not state.crime_ready:
        return False
    sections = crime_actions_enabled(profile)
    if not sections:
        return state.crime_ready
    ready_map = {
        "enkel": state.crime_enkel_ready,
        "tung": state.crime_tung_ready,
        "stjel": state.crime_stjel_ready,
    }
    return any(ready_map.get(section, state.crime_ready) for section in sections)


def gameplay_paused(profile: BotProfile, state) -> bool:
    if not profile.pause_on_restricted_status:
        return False
    return state.gameplay_restricted()
