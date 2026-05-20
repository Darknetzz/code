"""Pre-run checks before starting autopilot."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from mafibot.config import get_config_dir, get_pages_config_path
from mafibot.fixtures import verification_summary


@dataclass
class PreflightCheck:
    id: str
    ok: bool
    message: str
    hint: str = ""


@dataclass
class PreflightResult:
    ok: bool
    checks: list[PreflightCheck] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "checks": [
                {"id": c.id, "ok": c.ok, "message": c.message, "hint": c.hint}
                for c in self.checks
            ],
            "warnings": self.warnings,
            "verification": verification_summary().to_dict(),
        }


def _pages_json_age_days(path: Path) -> float | None:
    if not path.is_file():
        return None
    import time

    age_sec = time.time() - path.stat().st_mtime
    return age_sec / 86400.0


def run_preflight_checks(
    *,
    require_verification: bool = False,
    skip_verify: bool = False,
) -> PreflightResult:
    """Static checks (login must be verified separately when browser is open)."""
    checks: list[PreflightCheck] = []
    warnings: list[str] = []

    config_dir = get_config_dir()
    checks.append(
        PreflightCheck(
            id="config_dir",
            ok=config_dir.is_dir(),
            message=f"Config directory exists: {config_dir}",
            hint="Run login once to create profile data",
        )
    )

    pages_path = get_pages_config_path()
    pages_ok = pages_path.is_file()
    age = _pages_json_age_days(pages_path) if pages_ok else None
    msg = f"pages.json: {pages_path}" if pages_ok else "pages.json missing"
    checks.append(
        PreflightCheck(
            id="pages_json",
            ok=pages_ok,
            message=msg,
            hint="Run: python mafibot.py discover --accept-tos",
        )
    )
    if pages_ok and age is not None and age > 30:
        warnings.append(f"pages.json is {age:.0f} days old — consider re-running discover")

    verify = verification_summary()
    verify_ok = verify.ok if verify.run_dir else False
    if skip_verify:
        checks.append(
            PreflightCheck(
                id="verification",
                ok=True,
                message="Verification skipped",
            )
        )
    else:
        if verify.run_dir is None:
            checks.append(
                PreflightCheck(
                    id="verification",
                    ok=not require_verification,
                    message="No discovery run on disk",
                    hint="Run discover, then verify-pages or promote-fixtures",
                )
            )
        else:
            detail = (
                f"Discovery {verify.run_dir.name}: "
                f"{verify.failed_checks} failed checks, {verify.missing_html} missing HTML"
            )
            checks.append(
                PreflightCheck(
                    id="verification",
                    ok=verify_ok or not require_verification,
                    message=detail,
                    hint=(
                        "Fix selectors in mafibot/selectors.py; re-run discover"
                        if not verify_ok
                        else ""
                    ),
                )
            )
            if not verify_ok:
                warnings.append(
                    "Latest verification has failures — autopilot may mis-click"
                )

    ok = all(c.ok for c in checks)
    return PreflightResult(ok=ok, checks=checks, warnings=warnings)


def parse_error_playbook(parse_error: dict[str, str | None] | None) -> str:
    """Human hints when DOM parsing fails."""
    if not parse_error:
        return ""
    code = parse_error.get("code") or "parse_failed"
    hints = {
        "parse_failed": "Re-run discover and verify-pages; update selectors.py for changed labels.",
        "body_read_failed": "Browser may have lost the page — refresh login or restart the session.",
        "not_logged_in": "Complete mafibot.py login or use the Login tab.",
    }
    base = hints.get(code, hints["parse_failed"])
    shot = parse_error.get("screenshot_path")
    if shot:
        base += f" Screenshot: {shot}"
    return base
