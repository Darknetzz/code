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


def crime_entry_labels(profile: BotProfile) -> tuple[str, ...]:
    if profile.crime_kind == "steal":
        return ("stjel", "tyveri")
    return ("utfør", "begå")


def crime_perform_variant_labels(profile: BotProfile) -> tuple[str, ...]:
    if profile.crime_kind != "perform":
        return ()
    if profile.crime_perform_type == "lett":
        return ("lett kriminalitet", "lett", "enkel kriminalitet", "enkel")
    if profile.crime_perform_type == "tung":
        return ("tung kriminalitet", "tung")
    return ()


def crime_steal_item_labels(profile: BotProfile) -> tuple[str, ...]:
    what = (profile.crime_steal_what or "").strip()
    if not what:
        return ()
    return (what,)


def crime_steal_target_mode(profile: BotProfile) -> str:
    return profile.crime_steal_target_mode


def crime_steal_username(profile: BotProfile) -> str:
    return profile.crime_steal_username.strip()


def crime_submit_labels(profile: BotProfile) -> tuple[str, ...]:
    labels = [lb.strip() for lb in profile.crime_button_labels if lb.strip()]
    if labels:
        return tuple(labels)
    return ("utfør", "stjel", "begå", "gjør", "bekreft", "ok")


def crime_button_labels(profile: BotProfile) -> tuple[str, ...]:
    """Legacy helper — prefer crime_entry_labels + crime_submit_labels."""
    if profile.crime_button_labels:
        return crime_submit_labels(profile)
    if profile.crime_kind == "steal":
        return crime_entry_labels(profile) + crime_submit_labels(profile)
    entry = crime_entry_labels(profile)
    submit = crime_submit_labels(profile)
    return entry + submit


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
