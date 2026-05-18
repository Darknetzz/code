"""Murder target list helpers."""

from __future__ import annotations

from mafibot.config import BotProfile

_murder_rotate_index = 0


def reset_indices() -> None:
    global _murder_rotate_index
    _murder_rotate_index = 0


def murder_target_names(profile: BotProfile) -> list[str]:
    return [t.strip() for t in profile.murder_targets if t and t.strip()]


def pick_murder_target(profile: BotProfile) -> str | None:
    global _murder_rotate_index
    names = murder_target_names(profile)
    if not names:
        return None
    if profile.murder_rotate_targets and len(names) > 1:
        name = names[_murder_rotate_index % len(names)]
        _murder_rotate_index += 1
        return name
    return names[0]
