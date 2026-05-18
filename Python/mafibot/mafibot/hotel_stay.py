"""Hotel-first strategy: stay checked in; leave only briefly for blocked actions."""

from __future__ import annotations

# Actions that need leaving the hotel on ms.php (crime UI disabled in hotel).
ACTIONS_REQUIRING_LEAVE: frozenset[str] = frozenset(
    {
        "crime",
        "travel",
        "drugs",
        "murder",
        "bank",
    }
)

# Usually available from sidebar while still in hotel.
ACTIONS_OK_IN_HOTEL: frozenset[str] = frozenset(
    {
        "business",
        "ship",
        "messages",
        "family",
    }
)


def action_requires_leave_hotel(action_name: str) -> bool:
    return action_name in ACTIONS_REQUIRING_LEAVE


def should_skip_booking(state) -> bool:
    """Already checked into hotel (crime blocked = protected)."""
    return bool(state.in_hotel and state.hotel_blocks_actions)
