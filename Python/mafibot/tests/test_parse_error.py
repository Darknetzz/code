from mafibot.state import ParseError, parse_hotel_booking_hint


def test_parse_error_to_dict():
    err = ParseError("fail", code="body_read_failed", screenshot_path="/tmp/x.png")
    d = err.to_dict()
    assert d["code"] == "body_read_failed"
    assert d["screenshot_path"] == "/tmp/x.png"


def test_hotel_booking_hint():
    assert parse_hotel_booking_hint("Hotell er fullt") == "hotel_full"
    assert parse_hotel_booking_hint("Du har ikke nok penger") == "insufficient_funds"
    assert parse_hotel_booking_hint("Velkommen") is None
