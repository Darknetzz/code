"""Audit discovery HTML against selectors and crime_catalog labels."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from mafibot.config import get_discovery_dir
from mafibot.crime_catalog import SECTIONS
from mafibot.discover_diff import _normalize_html
from mafibot.selectors import (
    DEFAULT_SIDES,
    GAME_TABS,
    HOSPITAL_ACTION_LABELS,
    HOTEL_BOOK_LABELS,
    HOTEL_LEAVE_LABELS,
    MESSAGE_REPLY_LABELS,
    MURDER_ACTION_LABELS,
    NAV_LINKS,
    SHIP_ACTION_LABELS,
    SIDEBAR_LINKS,
    TRAVEL_ACTION_LABELS,
    WORK_ACTION_LABELS,
    DRUGS_ACTION_LABELS,
)

# Bot actions and how discovery names their HTML files.
ACTION_PAGES: tuple[str, ...] = (
    "crime",
    "travel",
    "hotel",
    "business",
    "ship",
    "drugs",
    "bank",
    "hospital",
    "messages",
    "family",
    "murder",
)

# Pages captured via sidebar navigation (separate HTML filename).
SIDEBAR_ACTION_PAGES: frozenset[str] = frozenset({"ship", "drugs", "murder", "business"})


@dataclass
class CheckResult:
    label: str
    status: str  # PASS | FAIL | SKIP
    detail: str = ""


@dataclass
class PageAudit:
    logical: str
    html_path: Path | None
    results: list[CheckResult] = field(default_factory=list)

    @property
    def failed(self) -> list[CheckResult]:
        return [r for r in self.results if r.status == "FAIL"]

    @property
    def ok(self) -> bool:
        return bool(self.results) and not self.failed and self.html_path is not None


def _text_contains(html: str, needle: str) -> bool:
    return needle.lower() in html.lower()


def _any_contains(html: str, needles: tuple[str, ...]) -> bool:
    return any(_text_contains(html, n) for n in needles)


def _crime_requirements() -> list[tuple[str, tuple[str, ...]]]:
    reqs: list[tuple[str, tuple[str, ...]]] = []
    for section in SECTIONS.values():
        for opt in section.options:
            labels = (opt.label, *opt.patterns)
            reqs.append((f"crime:{section.id}:{opt.id}", labels))
        reqs.append((f"crime:{section.id}:submit", section.submit_labels))
    return reqs


def _nav_requirements(logical: str) -> list[tuple[str, tuple[str, ...]]]:
    reqs: list[tuple[str, tuple[str, ...]]] = []
    tab = GAME_TABS.get(logical)
    if tab:
        reqs.append((f"nav:tab:{logical}", (tab,)))
    patterns = SIDEBAR_LINKS.get(logical) or NAV_LINKS.get(logical, ())
    if patterns:
        reqs.append((f"nav:sidebar:{logical}", patterns))
    return reqs


def _requirements_for(logical: str) -> list[tuple[str, tuple[str, ...]]]:
    if logical == "crime":
        return _crime_requirements()
    reqs = _nav_requirements(logical)
    if logical == "travel":
        reqs.append(("travel:submit", TRAVEL_ACTION_LABELS))
    elif logical == "hotel":
        reqs.append(("hotel:book", HOTEL_BOOK_LABELS + ("sjekk inn på", "overnatt")))
        reqs.append(("hotel:leave", HOTEL_LEAVE_LABELS))
    elif logical == "business":
        reqs.append(("business:action", WORK_ACTION_LABELS))
    elif logical == "ship":
        reqs.append(("ship:action", SHIP_ACTION_LABELS))
    elif logical == "drugs":
        reqs.append(("drugs:action", DRUGS_ACTION_LABELS))
    elif logical == "bank":
        reqs.append(("bank:deposit", ("innskudd", "sett inn")))
        reqs.append(("bank:withdraw", ("uttak", "ta ut")))
    elif logical == "hospital":
        reqs.append(("hospital:action", HOSPITAL_ACTION_LABELS))
    elif logical == "messages":
        reqs.append(("messages:open", ("les", "åpne", "innboks", "meldinger")))
        # Reply controls appear on an opened message, not the inbox list.
        reqs.append(("messages:reply", MESSAGE_REPLY_LABELS + ("svar på",)))
    elif logical == "family":
        reqs.append(("family:accept", ("godta", "aksepter")))
    elif logical == "murder":
        reqs.append(("murder:action", MURDER_ACTION_LABELS))
        reqs.append(
            (
                "murder:input",
                ("spiller", "brukernavn", 'name="spiller"', "motstander"),
            )
        )
    return reqs


def audit_html(logical: str, html: str) -> PageAudit:
    audit = PageAudit(logical=logical, html_path=None)
    for check_id, needles in _requirements_for(logical):
        if _any_contains(html, needles):
            audit.results.append(CheckResult(check_id, "PASS"))
        else:
            audit.results.append(
                CheckResult(
                    check_id,
                    "FAIL",
                    f"none of {needles!r} found in page text",
                )
            )
    return audit


def find_latest_discovery_run(base: Path | None = None) -> Path | None:
    root = base or get_discovery_dir()
    if not root.is_dir():
        return None
    runs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name)
    return runs[-1] if runs else None


def resolve_html_path(run_dir: Path, logical: str) -> Path | None:
    """Prefer action-specific snapshot; fall back to tab page name."""
    for name in (logical,):
        path = run_dir / f"{name}.html"
        if path.is_file():
            return path
    return None


def run_verification(
    discovery_dir: Path | None = None,
    *,
    pages: tuple[str, ...] = ACTION_PAGES,
) -> tuple[Path, list[PageAudit]]:
    run_dir = discovery_dir or find_latest_discovery_run()
    if run_dir is None or not run_dir.is_dir():
        raise FileNotFoundError(
            "No discovery run found. Run: python mafibot.py discover --accept-tos"
        )

    audits: list[PageAudit] = []
    for logical in pages:
        html_path = resolve_html_path(run_dir, logical)
        if html_path is None:
            audits.append(
                PageAudit(
                    logical=logical,
                    html_path=None,
                    results=[
                        CheckResult(
                            f"missing:{logical}",
                            "FAIL",
                            f"No {logical}.html in {run_dir}",
                        )
                    ],
                )
            )
            continue
        raw = html_path.read_text(encoding="utf-8", errors="replace")
        html = _normalize_html(raw)
        audit = audit_html(logical, html)
        audit.html_path = html_path
        audits.append(audit)

    report_path = run_dir / "verification_report.md"
    report_path.write_text(
        format_verification_report(run_dir, audits),
        encoding="utf-8",
    )
    return report_path, audits


def format_verification_report(run_dir: Path, audits: list[PageAudit]) -> str:
    lines = [
        "# Verification report",
        "",
        f"Discovery run: `{run_dir.name}`",
        "",
    ]
    total_fail = sum(len(a.failed) for a in audits)
    missing = sum(1 for a in audits if a.html_path is None)
    lines.append(f"**Summary:** {len(audits)} pages, {missing} missing HTML, {total_fail} failed checks")
    lines.append("")

    for audit in audits:
        status = "PASS" if audit.ok else "FAIL"
        lines.append(f"## {audit.logical} — {status}")
        if audit.html_path:
            lines.append(f"Source: `{audit.html_path.name}`")
        lines.append("")
        for r in audit.results:
            mark = {"PASS": "ok", "FAIL": "FAIL", "SKIP": "skip"}.get(r.status, r.status)
            line = f"- [{mark}] `{r.label}`"
            if r.detail:
                line += f" — {r.detail}"
            lines.append(line)
        lines.append("")

    failed_labels: list[str] = []
    for audit in audits:
        for r in audit.failed:
            failed_labels.append(f"{audit.logical}:{r.label}")
    if failed_labels:
        lines.append("## Suggested selector updates")
        lines.append("")
        lines.append("Review failed checks in `mafibot/selectors.py` and `mafibot/crime_catalog.py`.")
        lines.append("")

    return "\n".join(lines)


def verification_exit_code(audits: list[PageAudit]) -> int:
    if any(a.html_path is None for a in audits):
        return 1
    if any(a.failed for a in audits):
        return 1
    return 0
