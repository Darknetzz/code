from pathlib import Path

from mafibot.preflight import parse_error_playbook, run_preflight_checks


def test_preflight_missing_pages_json(tmp_path, monkeypatch):
    from mafibot import preflight as pf_mod

    tmp_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pf_mod, "get_config_dir", lambda: tmp_path)
    monkeypatch.setattr(pf_mod, "get_pages_config_path", lambda: tmp_path / "pages.json")
    result = run_preflight_checks(skip_verify=True)
    assert not result.ok
    assert any(c.id == "pages_json" and not c.ok for c in result.checks)


def test_parse_error_playbook_includes_screenshot():
    text = parse_error_playbook(
        {
            "code": "parse_failed",
            "detail": "missing rank",
            "screenshot_path": "/tmp/x.png",
        }
    )
    assert "discover" in text.lower()
    assert "/tmp/x.png" in text
