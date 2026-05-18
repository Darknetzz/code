"""Compare discovery HTML snapshots to fixtures and prior runs."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from mafibot.selectors import GAME_TABS


def _normalize_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.I | re.S)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compare_html_files(path_a: Path, path_b: Path) -> list[str]:
    """Unified diff lines between two HTML files."""
    a = _normalize_html(path_a.read_text(encoding="utf-8", errors="replace"))
    b = _normalize_html(path_b.read_text(encoding="utf-8", errors="replace"))
    return list(
        difflib.unified_diff(
            a.splitlines(),
            b.splitlines(),
            fromfile=str(path_a.name),
            tofile=str(path_b.name),
            lineterm="",
        )
    )


def find_previous_discovery_run(current: Path) -> Path | None:
    parent = current.parent
    if parent.name == "discovery":
        runs = sorted(
            (p for p in parent.iterdir() if p.is_dir() and p != current),
            key=lambda p: p.name,
        )
        return runs[-1] if runs else None
    siblings = sorted(
        (p for p in parent.parent.iterdir() if p.is_dir() and p != current),
        key=lambda p: p.name,
    )
    return siblings[-1] if siblings else None


def write_discovery_report(run_dir: Path, tabs_json: list[dict] | None = None) -> Path:
    """Write discovery_report.md summarizing tab coverage."""
    lines = ["# Discovery report", "", f"Run: `{run_dir.name}`", ""]
    known_labels = {v.lower() for v in GAME_TABS.values()}
    found: list[str] = []
    unknown: list[str] = []
    if tabs_json:
        for t in tabs_json:
            label = (t.get("label") or "").strip()
            if not label:
                continue
            found.append(label)
            if label.lower() not in known_labels and not any(
                k in label.lower() for k in known_labels
            ):
                unknown.append(label)
    lines.append("## Tabs seen")
    for label in found:
        lines.append(f"- {label}")
    if unknown:
        lines.append("")
        lines.append("## Unknown vs selectors.GAME_TABS")
        for label in unknown:
            lines.append(f"- {label}")
    prev = find_previous_discovery_run(run_dir)
    if prev:
        lines.extend(["", f"## Compare to previous (`{prev.name}`)", ""])
        for html in sorted(run_dir.glob("*.html")):
            other = prev / html.name
            if not other.is_file():
                lines.append(f"- `{html.name}`: new in this run")
                continue
            diff = compare_html_files(html, other)
            if len(diff) <= 2:
                lines.append(f"- `{html.name}`: unchanged")
            else:
                lines.append(f"- `{html.name}`: **changed** ({len(diff)} diff lines)")
    report = run_dir / "discovery_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
