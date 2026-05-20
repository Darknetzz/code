from mafibot.session_metrics import SessionMetrics, start_session_metrics, finish_session_metrics


def test_session_metrics_roundtrip(tmp_path, monkeypatch):
    from mafibot import session_metrics as sm

    monkeypatch.setattr(sm, "get_config_dir", lambda: tmp_path)
    m = start_session_metrics("ranker", dry_run=True)
    m.actions_run = 3
    m.record_hotel_sample(True)
    m.record_hotel_sample(False)
    finished = finish_session_metrics(money_end=1000, stop_reason="user stop")
    assert finished is not None
    assert finished.actions_run == 3
    loaded = sm.load_last_session_summary()
    assert loaded and loaded.profile == "ranker"
    assert loaded.money_end == 1000
    history = sm.load_session_history(limit=5)
    assert len(history) == 1
    assert history[0].profile == "ranker"


def test_record_hotel_skip():
    m = SessionMetrics()
    m.record_hotel_skip("insufficient_funds")
    m.record_hotel_skip("hotel_full")
    assert m.hotel_skip_insufficient_funds == 1
    assert m.hotel_skip_hotel_full == 1
