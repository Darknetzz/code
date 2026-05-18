"""Resolve per-action settings from BotProfile."""

from __future__ import annotations

from mafibot.config import BotProfile


def messages_interval_minutes(profile: BotProfile) -> int:
    return profile.messages_interval_minutes or profile.social_interval_minutes


def family_interval_minutes(profile: BotProfile) -> int:
    return profile.family_interval_minutes or profile.social_interval_minutes


def crime_min_health_percent(profile: BotProfile) -> int:
    if profile.crime_min_health_percent is not None:
        return profile.crime_min_health_percent
    return profile.min_health_percent


def crime_button_labels(profile: BotProfile) -> tuple[str, ...]:
    labels = [lb.strip() for lb in profile.crime_button_labels if lb.strip()]
    if labels:
        return tuple(labels)
    if profile.build == "angriper":
        return ("utfør", "stjel", "begå", "gjør", "tung")
    if profile.build == "okonom":
        return ("stjel", "tyveri", "utfør", "begå", "gjør")
    return ("utfør", "stjel", "begå", "gjør")


def drugs_click_labels(profile: BotProfile, location: str | None = None) -> tuple[str, ...]:
    from mafibot.drugs_locations import drugs_click_labels_for_location

    if location is not None:
        return drugs_click_labels_for_location(profile, location)
    prefer = profile.drugs_prefer
    if prefer == "buy":
        return ("kjøp",)
    if prefer == "sell":
        return ("selg",)
    return ("kjøp", "selg", "narkotika")
