"""Reset module-level action rotation indices (tests and new sessions)."""

from __future__ import annotations


def reset_rotation_state() -> None:
    from mafibot import action_targets, crime_catalog

    crime_catalog.reset_indices()
    action_targets.reset_indices()
