"""Regression tests for discovery HTML vs selector alignment."""

from __future__ import annotations

from pathlib import Path

import pytest

from mafibot.verify_pages import (
    ACTION_PAGES,
    audit_html,
    run_verification,
    verification_exit_code,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "discovered"


@pytest.mark.parametrize("logical", ACTION_PAGES)
def test_discovered_fixture_aligns(logical: str) -> None:
    path = FIXTURES / f"{logical}.html"
    assert path.is_file(), f"missing fixture {path.name}"
    html = path.read_text(encoding="utf-8")
    audit = audit_html(logical, html)
    assert not audit.failed, [
        (r.label, r.detail) for r in audit.failed
    ]


def test_run_verification_on_fixture_dir(tmp_path: Path) -> None:
    for logical in ("crime", "hotel"):
        src = FIXTURES / f"{logical}.html"
        (tmp_path / f"{logical}.html").write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    report, audits = run_verification(tmp_path, pages=("crime", "hotel"))
    assert report.is_file()
    assert verification_exit_code(audits) == 0


def test_optional_crime_marked_skip() -> None:
    html = "<body>Enkel kriminalitet Bryt opp en spilleautomat Ran en kiosk Utfør!</body>"
    audit = audit_html("crime", html)
    gate = next(r for r in audit.results if r.label == "crime:enkel:gate")
    assert gate.status == "SKIP"
