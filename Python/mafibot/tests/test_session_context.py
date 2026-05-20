from mafibot.brain import clear_stop, get_dry_run_decisions, request_stop
from mafibot.session_context import SessionContext


def test_session_context_dry_run_log():
    ctx = SessionContext()
    ctx.record_dry_run("crime", "selected: crime", hotel_steps="book→action→book")
    assert len(ctx.dry_run_decisions) == 1
    assert ctx.dry_run_decisions[0].action == "crime"


def test_brain_clear_stop_resets_context():
    clear_stop()
    request_stop()
    from mafibot.brain import is_stop_requested

    assert is_stop_requested()
    clear_stop()
    assert not is_stop_requested()
    assert get_dry_run_decisions() == []
