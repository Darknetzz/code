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
        "hospital",
        "messages",
        "family",
    }
)


def action_requires_leave_hotel(action_name: str) -> bool:
    return action_name in ACTIONS_REQUIRING_LEAVE


def should_skip_booking(state) -> bool:
    """Already checked into hotel (crime blocked = protected)."""
    return bool(state.in_hotel and state.hotel_blocks_actions)


def hotel_booking_blocked_reason(state, profile) -> str | None:
    """Skip booking when broke or hotel unavailable (parsed from last page text)."""
    from mafibot.state import parse_hotel_booking_hint

    sample = getattr(state, "page_text_sample", "") or ""
    hint = parse_hotel_booking_hint(sample)
    if hint == "insufficient_funds":
        return "insufficient_funds"
    if hint == "hotel_full":
        return "hotel_full"
    if profile.stay_in_hotel and state.money is not None and state.money < 500:
        return "low_wallet"
    return None
