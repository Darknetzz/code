"""Reset module-level action rotation indices (tests and new sessions)."""

from __future__ import annotations


def reset_rotation_state() -> None:
    from mafibot import action_targets, crime_catalog
    from mafibot.human_policy import reset_mouse_position

    crime_catalog.reset_indices()
    action_targets.reset_indices()
    from mafibot.assist_alerts import reset_assist_alerts
    from mafibot.city_rotation import reset_rotation_clock

    reset_assist_alerts()
    reset_rotation_clock()
    reset_mouse_position()
