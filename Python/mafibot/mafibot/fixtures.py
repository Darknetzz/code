"""Promote discovery HTML into test fixtures and summarize verification."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from mafibot.config import get_discovery_dir
from mafibot.verify_pages import (
    ACTION_PAGES,
    PageAudit,
    find_latest_discovery_run,
    resolve_html_path,
    run_verification,
    verification_exit_code,
)


@dataclass
class VerificationSummary:
    run_dir: Path | None
    report_path: Path | None = None
    pages: int = 0
    missing_html: int = 0
    failed_checks: int = 0
    ok: bool = False
    failed_labels: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "run_dir": str(self.run_dir) if self.run_dir else None,
            "report_path": str(self.report_path) if self.report_path else None,
            "pages": self.pages,
            "missing_html": self.missing_html,
            "failed_checks": self.failed_checks,
            "ok": self.ok,
            "failed_labels": self.failed_labels,
        }


def verification_summary(discovery_dir: Path | None = None) -> VerificationSummary:
    """Summarize latest (or given) discovery verification without raising."""
    run_dir = discovery_dir or find_latest_discovery_run()
    if run_dir is None or not run_dir.is_dir():
        return VerificationSummary(run_dir=None, ok=False)

    try:
        report_path, audits = run_verification(run_dir)
    except FileNotFoundError:
        return VerificationSummary(run_dir=run_dir, ok=False)

    failed_labels: list[str] = []
    for audit in audits:
        for r in audit.failed:
            failed_labels.append(f"{audit.logical}:{r.label}")

    missing = sum(1 for a in audits if a.html_path is None)
    fail_count = sum(len(a.failed) for a in audits)
    return VerificationSummary(
        run_dir=run_dir,
        report_path=report_path,
        pages=len(audits),
        missing_html=missing,
        failed_checks=fail_count,
        ok=verification_exit_code(audits) == 0,
        failed_labels=failed_labels,
    )


def _redact_html(text: str) -> str:
    return re.sub(r'value="[a-f0-9]{32}"', 'value="REDACTED"', text)


def promote_discovery_fixtures(
    discovery_dir: Path | None = None,
    *,
    dest: Path | None = None,
) -> tuple[Path, list[str]]:
    """Copy discovery HTML into tests/fixtures/discovered (redact tokens)."""
    run_dir = discovery_dir or find_latest_discovery_run()
    if run_dir is None or not run_dir.is_dir():
        raise FileNotFoundError(
            "No discovery run found. Run: python mafibot.py discover --accept-tos"
        )

    if dest is None:
        dest = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "discovered"
    dest.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for logical in ACTION_PAGES:
        src = resolve_html_path(run_dir, logical)
        if src is None or not src.is_file():
            raise FileNotFoundError(f"Missing {logical}.html in {run_dir}")
        text = _redact_html(src.read_text(encoding="utf-8", errors="replace"))
        out = dest / f"{logical}.html"
        out.write_text(text, encoding="utf-8")
        copied.append(logical)

    return dest, copied
