#!/usr/bin/env python3
"""
SizeTree - A TreeSize-like disk space analyzer
Built with Textual for interactive TUI and CLI support
"""

import colorsys
import html
import json
import math
import sys
import tempfile
import time
import webbrowser
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from rich.tree import Tree as RichTree
from rich.progress import Progress, SpinnerColumn, TextColumn

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal, VerticalScroll
from textual.widgets import Header, Footer, Tree, Static, Label
from textual.binding import Binding

__version__ = "1.0.0"

_CLI_EPILOG = (
    "[bold]Examples:[/bold]\n\n"
    "[cyan]pytree .[/cyan] - scan current dir (shortcut for 'pytree scan .').\n\n"
    "[cyan]pytree scan ~/code -d 2 -l 30 -t[/cyan] - tree view, depth 2, top 30 entries.\n\n"
    "[cyan]pytree report D:\\ -o sizes.html[/cyan] - write HTML report and open it in a browser.\n\n"
    "[cyan]pytree report . --format json -o out.json[/cyan] - machine-readable report "
    "(text / json / markdown / html).\n\n"
    "[cyan]pytree tui ~/Downloads[/cyan] - interactive explorer (arrow keys, enter to drill in).\n\n"
    "Run [cyan]pytree <command> --help[/cyan] for all flags of a given command."
)

app = typer.Typer(
    rich_markup_mode="rich",
    help=(
        "Disk space analyzer (CLI + TUI). "
        "Commands: [cyan]scan[/cyan] (terminal view), [cyan]report[/cyan] "
        "(HTML / JSON / Markdown / text file, opens HTML in browser by default), "
        "[cyan]tui[/cyan] (interactive explorer), [cyan]version[/cyan]."
    ),
    epilog=_CLI_EPILOG,
)
console = Console()


def _print_version() -> None:
    """Print the pytree version banner. Single source of truth for version output."""
    console.print(f"[bold]SizeTree[/bold] v{__version__}")
    console.print("A TreeSize-like disk space analyzer built with Textual")


def _version_callback(value: bool) -> None:
    if value:
        _print_version()
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show version and exit.",
        is_eager=True,
        callback=_version_callback,
    ),
) -> None:
    """Root callback so --version works without a subcommand."""
    return

# ─────────────────────────────────────────────────────────────────────── #
#                              DATA STRUCTURES                            #
# ─────────────────────────────────────────────────────────────────────── #

@dataclass
class DirInfo:
    """Directory information with size and file counts."""
    path: Path
    size: int  # in bytes
    file_count: int
    dir_count: int
    children: List['DirInfo']
    error: Optional[str] = None

    @property
    def name(self) -> str:
        return self.path.name or str(self.path)

    def format_size(self) -> str:
        """Format size in human-readable format."""
        size = float(self.size)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"


def entry_is_directory(info: DirInfo) -> bool:
    """Whether this row is a directory. Uses the path so empty dirs are still dirs."""
    try:
        return info.path.is_dir()
    except OSError:
        return bool(info.children)


# ─────────────────────────────────────────────────────────────────────── #
#                              SCANNING LOGIC                             #
# ─────────────────────────────────────────────────────────────────────── #

@dataclass
class ScanStats:
    """Live counters updated during a scan. Shared across the full recursion."""
    files: int = 0
    dirs: int = 0
    size: int = 0
    current: str = ""


ProgressCb = Callable[[ScanStats], None]


def scan_directory(
    path: Path,
    max_depth: Optional[int] = None,
    current_depth: int = 0,
    *,
    stats: Optional[ScanStats] = None,
    progress_cb: Optional[ProgressCb] = None,
) -> DirInfo:
    """Recursively scan directory and calculate sizes.

    If ``stats`` + ``progress_cb`` are supplied, ``progress_cb(stats)`` is
    called after each file/dir is seen so callers (CLI/TUI) can render live
    progress. Throttling is the caller's responsibility so the scanner stays
    as fast as possible.
    """
    if stats is None:
        stats = ScanStats()
    total_size = 0
    file_count = 0
    dir_count = 0
    children = []
    error = None

    if progress_cb is not None:
        stats.current = str(path)
        progress_cb(stats)

    try:
        items = list(path.iterdir())

        for item in items:
            try:
                if item.is_file():
                    sz = item.stat().st_size
                    total_size += sz
                    file_count += 1
                    stats.files += 1
                    stats.size += sz
                    if progress_cb is not None:
                        progress_cb(stats)
                    # List files alongside dirs so table/tree show largest items in flat folders
                    children.append(
                        DirInfo(
                            path=item,
                            size=sz,
                            file_count=1,
                            dir_count=0,
                            children=[],
                        )
                    )
                elif item.is_dir():
                    dir_count += 1
                    stats.dirs += 1

                    # Recursively scan subdirectories if within depth limit
                    if max_depth is None or current_depth < max_depth:
                        child_info = scan_directory(
                            item,
                            max_depth,
                            current_depth + 1,
                            stats=stats,
                            progress_cb=progress_cb,
                        )
                        children.append(child_info)
                        total_size += child_info.size
                        file_count += child_info.file_count
                        dir_count += child_info.dir_count
                    else:
                        # Just get size without recursing
                        child_size = get_dir_size(item, stats=stats, progress_cb=progress_cb)
                        child_info = DirInfo(
                            path=item,
                            size=child_size,
                            file_count=0,
                            dir_count=0,
                            children=[]
                        )
                        children.append(child_info)
                        total_size += child_size

            except PermissionError:
                continue
            except Exception:
                continue

    except PermissionError:
        error = "Permission denied"
    except Exception as e:
        error = str(e)

    # Sort children by size (largest first)
    children.sort(key=lambda x: x.size, reverse=True)

    return DirInfo(
        path=path,
        size=total_size,
        file_count=file_count,
        dir_count=dir_count,
        children=children,
        error=error
    )


def get_dir_size(
    path: Path,
    *,
    stats: Optional[ScanStats] = None,
    progress_cb: Optional[ProgressCb] = None,
) -> int:
    """Get total size of directory without detailed recursion."""
    total = 0
    try:
        for item in path.rglob('*'):
            try:
                if item.is_file():
                    sz = item.stat().st_size
                    total += sz
                    if stats is not None:
                        stats.files += 1
                        stats.size += sz
                        if progress_cb is not None:
                            progress_cb(stats)
            except Exception:
                continue
    except Exception:
        pass
    return total


def make_throttled_progress_cb(
    progress: Progress,
    task_id: int,
    *,
    interval: float = 0.1,
) -> ProgressCb:
    """Return a progress callback that updates a rich ``Progress`` task at
    most every ``interval`` seconds, showing files/dirs/size scanned so far."""
    state = {"last": 0.0}

    def _cb(stats: ScanStats) -> None:
        now = time.monotonic()
        if now - state["last"] < interval:
            return
        state["last"] = now
        current = stats.current
        if len(current) > 60:
            current = "..." + current[-57:]
        progress.update(
            task_id,
            description=(
                f"Scanning  "
                f"[bold]{stats.files:,}[/bold] files  "
                f"[bold]{stats.dirs:,}[/bold] dirs  "
                f"[bold]{format_size(stats.size)}[/bold]  "
                f"[dim]{current}[/dim]"
            ),
        )

    return _cb


def format_size(size: int) -> str:
    """Format size in human-readable format."""
    size_float = float(size)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_float < 1024.0:
            return f"{size_float:.1f} {unit}"
        size_float /= 1024.0
    return f"{size_float:.1f} PB"


# Narrow no-break space — visually distinct from a decimal point, keeps
# numbers non-wrapping. Used only for HTML-facing count formatting so there's
# no chance of confusing integer counts like "73,898" with a float "73.898"
# in small pill fonts.
_COUNT_THOUSANDS_SEP = "\u202f"


def format_count(n: int) -> str:
    """Format an integer count with a narrow no-break space as the thousands
    separator. Integer-only by design: counts are never fractional."""
    return f"{int(n):,}".replace(",", _COUNT_THOUSANDS_SEP)


class ReportFormat(str, Enum):
    """Supported file report formats."""
    text = "text"
    json = "json"
    markdown = "markdown"
    html = "html"


def infer_report_format(path: Path) -> Optional[ReportFormat]:
    """Guess format from file extension."""
    suf = path.suffix.lower()
    if suf == ".json":
        return ReportFormat.json
    if suf in (".md", ".markdown"):
        return ReportFormat.markdown
    if suf in (".html", ".htm"):
        return ReportFormat.html
    if suf in (".txt", ""):
        return ReportFormat.text
    return None


def dir_info_to_json_dict(d: DirInfo) -> Dict[str, Any]:
    """Serialize DirInfo to a JSON-friendly dict."""
    return {
        "path": str(d.path),
        "name": d.name,
        "size_bytes": d.size,
        "size_human": d.format_size(),
        "file_count": d.file_count,
        "dir_count": d.dir_count,
        "error": d.error,
        "children": [dir_info_to_json_dict(c) for c in d.children],
    }


def build_plain_tree_lines(
    dir_info: DirInfo,
    limit: int,
    max_level: int = 3,
    current_level: int = 0,
) -> List[str]:
    """ASCII tree lines (no ANSI), aligned with build_rich_tree depth/limit."""
    lines: List[str] = []

    def walk(d: DirInfo, prefix: str, level: int) -> None:
        if level >= max_level:
            return
        children = d.children[:limit]
        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            branch = "└── " if is_last else "├── "
            err = f" [Error: {child.error}]" if child.error else ""
            lines.append(f"{prefix}{branch}{child.name} ({format_size(child.size)}){err}")
            ext = "    " if is_last else "│   "
            if child.children:
                walk(child, prefix + ext, level + 1)

    root_err = f" [Error: {dir_info.error}]" if dir_info.error else ""
    lines.append(f"{dir_info.name} ({format_size(dir_info.size)}){root_err}")
    walk(dir_info, "", current_level)
    return lines


def build_plain_table_lines(dir_info: DirInfo, target_path: Path, limit: int) -> List[str]:
    """Plain-text rows for largest-items table."""
    lines = [
        f"Largest Items in {target_path}",
        "",
        f"{'#':>4}  {'Name':<42}  {'Size':>12}  {'Files':>8}  {'Dirs':>6}  {'Type'}",
        "-" * 92,
    ]
    for i, child in enumerate(dir_info.children[:limit], 1):
        item_type = "Dir" if entry_is_directory(child) else "File"
        name = child.name if len(child.name) <= 42 else child.name[:39] + "..."
        lines.append(
            f"{i:>4}  {name:<42}  {format_size(child.size):>12}  "
            f"{child.file_count:>8,}  {child.dir_count:>6,}  {item_type}"
        )
    return lines


def render_report_text(
    dir_info: DirInfo,
    target_path: Path,
    *,
    tree_view: bool,
    limit: int,
) -> str:
    """Plain text report (summary + table or tree)."""
    header = [
        f"Scan: {target_path}",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Total Size: {format_size(dir_info.size)}",
        f"Files: {dir_info.file_count:,} | Directories: {dir_info.dir_count:,}",
        "",
    ]
    if tree_view:
        body = build_plain_tree_lines(dir_info, limit)
    else:
        body = build_plain_table_lines(dir_info, target_path, limit)
    return "\n".join(header + body) + "\n"


def render_report_markdown(
    dir_info: DirInfo,
    target_path: Path,
    *,
    tree_view: bool,
    limit: int,
) -> str:
    """Markdown report."""
    lines = [
        f"# Disk usage: `{target_path}`",
        "",
        f"- **Scanned:** `{target_path}`",
        f"- **Generated:** {datetime.now().isoformat(timespec='seconds')}",
        f"- **Total size:** {format_size(dir_info.size)}",
        f"- **Files:** {dir_info.file_count:,} · **Directories:** {dir_info.dir_count:,}",
        "",
    ]
    if tree_view:
        lines.append("## Tree")
        lines.append("")
        lines.append("```")
        lines.extend(build_plain_tree_lines(dir_info, limit))
        lines.append("```")
    else:
        lines.append("## Largest items")
        lines.append("")
        lines.append("| # | Name | Size | Files | Dirs | Type |")
        lines.append("|---:|------|------:|------:|-----:|------|")
        for i, child in enumerate(dir_info.children[:limit], 1):
            item_type = "Dir" if entry_is_directory(child) else "File"
            safe_name = child.name.replace("|", "\\|")
            lines.append(
                f"| {i} | {safe_name} | {format_size(child.size)} | "
                f"{child.file_count:,} | {child.dir_count:,} | {item_type} |"
            )
    lines.append("")
    return "\n".join(lines)


# Colors for donut / bar segments (dark-theme friendly)
_HTML_CHART_COLORS = (
    "#58a6ff",
    "#d2a8ff",
    "#79c0ff",
    "#3fb950",
    "#ffa657",
    "#f85149",
    "#a371f7",
    "#7ee787",
    "#ff7b72",
    "#d4a72c",
    "#79c0ff",
    "#db61a2",
)


def _svg_donut_slices(
    segments: List[Tuple[int, str, int]],
    total: int,
    *,
    cx: float = 100.0,
    cy: float = 100.0,
    outer_r: float = 78.0,
    inner_r: float = 44.0,
) -> str:
    """segments: (size_bytes, color_hex, viz_index). Returns SVG path elements."""
    if total <= 0 or not segments:
        return ""
    start = -math.pi / 2
    paths: List[str] = []
    for size, color, viz_idx in segments:
        if size <= 0:
            continue
        sweep = 2 * math.pi * (size / total)
        a0, a1 = start, start + sweep
        x0o, y0o = cx + outer_r * math.cos(a0), cy + outer_r * math.sin(a0)
        x1o, y1o = cx + outer_r * math.cos(a1), cy + outer_r * math.sin(a1)
        x0i, y0i = cx + inner_r * math.cos(a0), cy + inner_r * math.sin(a0)
        x1i, y1i = cx + inner_r * math.cos(a1), cy + inner_r * math.sin(a1)
        large = 1 if sweep > math.pi else 0
        paths.append(
            f'<path class="viz-donut-seg" data-viz-idx="{viz_idx}" tabindex="0" '
            f'd="M {x0o:.2f} {y0o:.2f} A {outer_r} {outer_r} 0 {large} 1 {x1o:.2f} {y1o:.2f} '
            f"L {x1i:.2f} {y1i:.2f} A {inner_r} {inner_r} 0 {large} 0 {x0i:.2f} {y0i:.2f} Z\" "
            f'fill="{color}" stroke="#0d1117" stroke-width="1"/>'
        )
        start = a1
    return "".join(paths)


def _html_storage_viz_block(dir_info: DirInfo, esc, limit: int) -> str:
    """Donut SVG + stacked bar + legend for direct children (interactive via JS)."""
    kids = list(dir_info.children[: max(limit, 24)])
    total = dir_info.size or 1
    if not kids:
        return '<p class="viz-empty">No direct items to chart.</p>'

    chart_items: List[Tuple[str, int, str]] = []
    for i, ch in enumerate(kids):
        chart_items.append((ch.name, ch.size, _HTML_CHART_COLORS[i % len(_HTML_CHART_COLORS)]))

    seg_data = [(sz, col, i) for i, (_nm, sz, col) in enumerate(chart_items)]
    paths = _svg_donut_slices(seg_data, total)

    viz_payload: List[Dict[str, Any]] = []
    for i, ch in enumerate(kids):
        nm, sz, col = chart_items[i]
        viz_payload.append(
            {
                "i": i,
                "name": ch.name,
                "size": ch.size,
                "human": ch.format_size(),
                "files": ch.file_count,
                "dirs": ch.dir_count,
                "isDir": entry_is_directory(ch),
                "color": col,
                "pctRoot": round(100.0 * sz / total, 4),
            }
        )
    json_text = json.dumps(viz_payload, ensure_ascii=False).replace("</", "<\\/")

    legend_rows = []
    for i, (name, size, color) in enumerate(chart_items):
        pct = 100.0 * size / total
        legend_rows.append(
            "<label class=\"legend-row viz-legend-row\" data-viz-idx=\"" + str(i) + "\">"
            "<input type=\"checkbox\" class=\"viz-filter-cb\" data-viz-idx=\"" + str(i) + "\" checked "
            'aria-label="Include in chart"/>'
            f"<span class=\"swatch\" style=\"background:{color}\"></span>"
            f"<span class=\"legend-name\">{esc(name)}</span>"
            f"<span class=\"legend-pct\">{pct:.1f}%</span>"
            f"<span class=\"legend-sz\">{esc(format_size(size))}</span>"
            "</label>"
        )

    stacked_parts = []
    for i, (name, size, color) in enumerate(chart_items):
        w = max(0.0, 100.0 * size / total)
        stacked_parts.append(
            f"<span class=\"viz-hbar-seg\" data-viz-idx=\"{i}\" style=\"width:{w:.3f}%;background:{color}\"></span>"
        )

    donut = (
        '<div class="donut-wrap" id="pytree-donut-wrap">'
        '<svg viewBox="0 0 200 200" class="donut-svg" id="pytree-donut-svg" '
        'role="img" aria-label="Storage share by item">'
        "<defs><filter id=\"pytree-donut-glow\"><feGaussianBlur stdDeviation=\"0.5\" result=\"b\"/>"
        "<feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter></defs>"
        f'<g id="pytree-donut-paths">{paths}</g>'
        "</svg>"
        '<p class="viz-donut-empty" id="pytree-donut-empty" hidden>No segments visible — enable items below.</p>'
        "</div>"
    )
    legend = '<div class="legend-col" id="pytree-legend-col">' + "\n".join(legend_rows) + "</div>"
    stacked = (
        '<div class="stacked-hbar" id="pytree-stacked-hbar" role="img" aria-label="Relative size of each item">'
        + "".join(stacked_parts)
        + "</div>"
    )
    toolbar = (
        '<div class="viz-toolbar">'
        '<button type="button" class="btn viz-tb-btn" id="viz-show-all" title="Include every item in the chart">'
        f'<span class="btn-icon">{_icon("eye", size=13, cls="chrome-icon")}</span>Show all</button> '
        '<button type="button" class="btn viz-tb-btn" id="viz-hide-all" title="Hide every segment (chart empty)">'
        f'<span class="btn-icon">{_icon("eye_slash", size=13, cls="chrome-icon")}</span>Hide all</button> '
        '<span class="viz-status" id="viz-filter-status"></span>'
        "</div>"
    )
    tooltip = '<div id="pytree-viz-tooltip" class="viz-tooltip" hidden></div>'
    return (
        '<div class="storage-viz" id="pytree-storage-viz">'
        f'<script type="application/json" id="pytree-viz-data">{json_text}</script>'
        f'<div class="viz-toolbar-wrap">{toolbar}</div>'
        f"{tooltip}"
        '<div class="storage-viz-top">'
        f"{donut}"
        f'<div class="viz-charts-col"><h3 class="viz-title">Share of scanned folder</h3>{stacked}</div>'
        "</div>"
        f'<div class="legend-col legend-col-full">{legend}</div>'
        "</div>"
    )


def _heat_bg(value: int, max_value: int) -> str:
    """Return a heat-map background color (green -> yellow -> red) for a cell.

    Uses a perceptual sqrt curve so mid-range values aren't all pale green.
    Returns an empty string when there's nothing meaningful to color.
    """
    if max_value <= 0 or value <= 0:
        return ""
    ratio = value / max_value
    if ratio < 0:
        ratio = 0.0
    elif ratio > 1:
        ratio = 1.0
    curved = ratio ** 0.5
    hue = 120.0 * (1.0 - curved)
    alpha = 0.12 + 0.38 * curved
    return f"hsla({hue:.0f}, 72%, 45%, {alpha:.3f})"


# ─────────────────────────────────────────────────────────────────────── #
#                              ICON LIBRARY                               #
# ─────────────────────────────────────────────────────────────────────── #
# Every icon is a single <path> on a 16×16 viewBox and uses
# ``fill="currentColor"`` so the surrounding CSS decides the color. One
# source of truth per shape, one helper to stamp them out at any size.

def _svg_icon(path_d: str, *, size: int = 14, cls: str = "icon-svg") -> str:
    return (
        f'<svg viewBox="0 0 16 16" width="{size}" height="{size}" '
        f'aria-hidden="true" class="{cls}">'
        f'<path fill="currentColor" d="{path_d}"/></svg>'
    )


# Octicons-derived path data (MIT-licensed shapes, trimmed to single paths).
_ICON_D = {
    "dir": (
        "M1.75 1h3.5c.28 0 .54.11.73.28l1.5 1.47h6.77c.97 0 1.75.78 1.75 "
        "1.75v8.75c0 .97-.78 1.75-1.75 1.75H1.75A1.75 1.75 0 0 1 0 13.25V2.75"
        "C0 1.78.78 1 1.75 1Z"
    ),
    "file": (
        "M2 1.75C2 .78 2.78 0 3.75 0h6.5a.75.75 0 0 1 .53.22l4.25 4.25c.14."
        "14.22.33.22.53v9.25A1.75 1.75 0 0 1 13.5 16h-9.75A1.75 1.75 0 0 1 2"
        " 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .14.11.25.25.25h9.75a."
        "25.25 0 0 0 .25-.25V6h-2.75A1.75 1.75 0 0 1 9.25 4.25V1.5Zm6.75.56"
        "v2.19c0 .14.11.25.25.25h2.19Z"
    ),
    "search": (
        "M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04"
        "a.749.749 0 0 1-1.06 1.06ZM11.5 7a4.499 4.499 0 1 0-8.997 0A4.499 "
        "4.499 0 0 0 11.5 7Z"
    ),
    "chevron_down": (
        "M12.78 5.22a.749.749 0 0 1 0 1.06l-4.25 4.25a.749.749 0 0 1-1.06 0"
        "L3.22 6.28a.749.749 0 1 1 1.06-1.06L8 8.939l3.72-3.719a.749.749 0 "
        "0 1 1.06 0Z"
    ),
    "chevron_up": (
        "M3.22 10.78a.749.749 0 0 1 0-1.06l4.25-4.25a.749.749 0 0 1 1.06 0l"
        "4.25 4.25a.749.749 0 1 1-1.06 1.06L8 7.061l-3.72 3.719a.749.749 0 "
        "0 1-1.06 0Z"
    ),
    "eye": (
        "M8 2c1.981 0 3.671.992 4.933 2.078 1.27 1.091 2.187 2.36 2.637 "
        "3.023a1.62 1.62 0 0 1 0 1.798c-.45.663-1.367 1.932-2.637 3.023C11"
        ".67 13.008 9.98 14 8 14c-1.981 0-3.671-.992-4.933-2.078C1.797 10."
        "83.88 9.56.43 8.898a1.62 1.62 0 0 1 0-1.798c.45-.663 1.367-1.932 "
        "2.637-3.023C4.33 2.992 6.02 2 8 2Zm0 2.5a3.5 3.5 0 1 0 0 7 3.5 3."
        "5 0 0 0 0-7ZM8 9.5a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3Z"
    ),
    "eye_slash": (
        "m.47 1.53 14 14a.75.75 0 1 0 1.06-1.06l-2.2-2.2c1.18-.9 2-1.94 2."
        "45-2.59a1.62 1.62 0 0 0 0-1.79c-.45-.66-1.37-1.93-2.64-3.03C11.88"
        " 3.78 10.06 2.75 8 2.75c-1.36 0-2.58.46-3.63 1.08L1.53.47A.75.75 "
        "0 0 0 .47 1.53ZM8 11.25a3.25 3.25 0 0 1-3.18-3.94L3.56 6.05a16.3 "
        "16.3 0 0 0-1.48 1.8 1.62 1.62 0 0 0 0 1.79c.45.66 1.37 1.93 2.64 "
        "3.03C5.96 13.85 6.94 14 8 14c.85 0 1.66-.17 2.43-.46l-1.25-1.26a3"
        ".22 3.22 0 0 1-1.18.22ZM8 5.25c.45 0 .88.09 1.26.26L6.52 8.26a3."
        "25 3.25 0 0 1 1.48-3.01Z"
    ),
    "label": (
        "M2.5 7.775V2.75a.25.25 0 0 1 .25-.25h5.025a.25.25 0 0 1 .177.073l"
        "6.25 6.25a.25.25 0 0 1 0 .354l-5.025 5.025a.25.25 0 0 1-.354 0l-6"
        ".25-6.25a.25.25 0 0 1-.073-.177Zm-1.5 0V2.75C1 1.784 1.784 1 2.75"
        " 1h5.025c.464 0 .91.184 1.238.513l6.25 6.25a1.75 1.75 0 0 1 0 2.4"
        "74l-5.026 5.026a1.75 1.75 0 0 1-2.474 0l-6.25-6.25A1.748 1.748 0 "
        "0 1 1 7.775ZM6 5a1 1 0 1 0 0 2 1 1 0 0 0 0-2Z"
    ),
    "pie": (
        "M8 0a8 8 0 1 1-3.2 15.33.75.75 0 1 1 .6-1.37A6.5 6.5 0 1 0 1.53 5"
        ".6a.75.75 0 1 1-1.36-.63A8 8 0 0 1 8 0Zm1.6 1.65A6.5 6.5 0 0 1 14"
        ".35 6.4.75.75 0 0 1 13.6 7.3H9.25a.75.75 0 0 1-.75-.75V2.2a.75.75"
        " 0 0 1 1.1-.55ZM10 3.76v1.74h1.74A5 5 0 0 0 10 3.76Z"
    ),
    "disk": (
        "M0 2.75C0 1.784.784 1 1.75 1h12.5c.966 0 1.75.784 1.75 1.75v3.5"
        "c0 .412-.144.79-.383 1.088.239.297.383.676.383 1.087v3.5A1.75 1."
        "75 0 0 1 14.25 13.75H1.75A1.75 1.75 0 0 1 0 12v-3.5c0-.411.144-."
        "79.383-1.087A1.742 1.742 0 0 1 0 6.25v-3.5Zm1.75-.25a.25.25 0 0 "
        "0-.25.25v3.5c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25v-3.5"
        "a.25.25 0 0 0-.25-.25H1.75ZM2.5 4.25a.75.75 0 0 1 .75-.75h1.5a."
        "75.75 0 0 1 0 1.5h-1.5a.75.75 0 0 1-.75-.75Zm9.25-.75a.75.75 0 "
        "0 0 0 1.5h.5a.75.75 0 0 0 0-1.5h-.5ZM1.5 12c0 .138.112.25.25.25"
        "h12.5a.25.25 0 0 0 .25-.25v-3.5a.25.25 0 0 0-.25-.25H1.75a.25."
        "25 0 0 0-.25.25V12Zm1.75-1.75a.75.75 0 0 1 .75.75.75.75 0 0 1-"
        ".75.75.75.75 0 0 1-.75-.75.75.75 0 0 1 .75-.75Zm9 0a.75.75 0 0"
        " 0 0 1.5h.5a.75.75 0 0 0 0-1.5h-.5Z"
    ),
    "folder_up": (
        "M0 2.75C0 1.784.784 1 1.75 1h3.502c.464 0 .91.184 1.238.513L7.7"
        "5 2.75h6.5c.966 0 1.75.784 1.75 1.75v8.75A1.75 1.75 0 0 1 14.25 "
        "15H1.75A1.75 1.75 0 0 1 0 13.25V2.75Zm8.53 6.53L7.25 8v3.75a.75"
        ".75 0 0 1-1.5 0V8L4.47 9.28a.75.75 0 0 1-1.06-1.06l2.5-2.5a.75."
        "75 0 0 1 1.06 0l2.5 2.5a.75.75 0 1 1-1.06 1.06Z"
    ),
    "expand_all": (
        "M3.97 4.03a.75.75 0 0 1 1.06 0L8 7l2.97-2.97a.75.75 0 1 1 1.06 "
        "1.06L8.53 8.53a.75.75 0 0 1-1.06 0L3.97 5.09a.75.75 0 0 1 0-1.0"
        "6Zm0 4a.75.75 0 0 1 1.06 0L8 11l2.97-2.97a.75.75 0 1 1 1.06 1.0"
        "6l-3.5 3.5a.75.75 0 0 1-1.06 0L3.97 9.09a.75.75 0 0 1 0-1.06Z"
    ),
    "collapse_all": (
        "M3.97 8.03a.75.75 0 0 0 1.06 0L8 5.06l2.97 2.97a.75.75 0 0 0 1."
        "06-1.06L8.53 3.47a.75.75 0 0 0-1.06 0L3.97 6.97a.75.75 0 0 0 0 "
        "1.06Zm0 4a.75.75 0 0 0 1.06 0L8 9.06l2.97 2.97a.75.75 0 0 0 1."
        "06-1.06l-3.5-3.5a.75.75 0 0 0-1.06 0l-3.5 3.5a.75.75 0 0 0 0 1"
        ".06Z"
    ),
}


def _icon(name: str, *, size: int = 14, cls: str = "icon-svg") -> str:
    return _svg_icon(_ICON_D[name], size=size, cls=cls)


# Canonical icons used in tree rows (kept as explicit names for clarity).
_SVG_ICON_DIR = _icon("dir")
_SVG_ICON_FILE = _icon("file")


def _pill(value_html: str, bg: str) -> str:
    """Wrap a value in a heat-pill span. If ``bg`` is empty (value is zero or
    the whole column is zero) we still render the pill, using the ``-zero``
    modifier so every row in a numeric column looks structurally identical."""
    if not bg:
        return f'<span class="heat-pill heat-pill-zero">{value_html}</span>'
    return f'<span class="heat-pill" style="background:{bg}">{value_html}</span>'


def _html_tree_rows(
    parent: DirInfo,
    esc,
    limit: int,
    max_depth: int,
    *,
    path_id: str = "",
    depth: int = 0,
    share_base: int,
    color_offset: int = 0,
) -> List[str]:
    """Flat list of ``<tr>`` rows for the contents table.

    Every item is a direct child of the outer ``<tbody>`` so columns are
    guaranteed to align at every depth. Parent-child relationships are
    encoded via ``data-path`` / ``data-parent`` and expand/collapse is
    driven by JS on the client side.
    """
    if depth >= max_depth:
        return []

    rows: List[str] = []
    base = max(share_base, 1)
    kids = parent.children[:limit]
    max_size = max((c.size for c in kids), default=0)
    max_files = max((c.file_count for c in kids), default=0)
    max_dirs = max((c.dir_count for c in kids), default=0)

    for i, child in enumerate(kids):
        is_dir = entry_is_directory(child)
        kind = "dir" if is_dir else "file"
        pct = 100.0 * child.size / base
        bar_color = _HTML_CHART_COLORS[(color_offset + i) % len(_HTML_CHART_COLORS)]

        child_path = f"{path_id}.{i}" if path_id else str(i)
        has_kids = is_dir and (depth + 1 < max_depth) and bool(child.children)

        is_top = depth == 0
        idx_html = f"{i + 1}" if is_top else ""
        idx_cell = f'<td class="num col-idx">{idx_html}</td>'

        expand_html = (
            '<button type="button" class="row-expand" aria-expanded="false" '
            'aria-label="Toggle folder contents"></button>'
            if has_kids
            else '<span class="row-expand-placeholder"></span>'
        )
        icon_html = (
            f'<span class="entry-icon" data-kind="{kind}">'
            f'{_SVG_ICON_DIR if is_dir else _SVG_ICON_FILE}</span>'
        )
        name_inner = (
            f'{expand_html}{icon_html}'
            f'<span class="entry-name">{esc(child.name)}</span>'
        )

        size_pill = _pill(esc(format_size(child.size)), _heat_bg(child.size, max_size))
        files_pill = _pill(format_count(child.file_count), _heat_bg(child.file_count, max_files))
        dirs_pill = _pill(format_count(child.dir_count), _heat_bg(child.dir_count, max_dirs))

        # Indent the name cell proportionally to depth. The expand
        # button/placeholder already takes a fixed slot, so we only add
        # indent per nesting level here.
        indent_rem = 0.75 + depth * 1.25
        hidden_attr = "" if is_top else " hidden"
        viz_idx_attr = f' data-viz-idx="{i}"' if is_top else ""

        rows.append(
            f'<tr class="item-row depth-{depth}"'
            f' data-path="{child_path}" data-parent="{path_id}"'
            f' data-depth="{depth}" data-is-dir="{1 if is_dir else 0}"'
            f' data-has-kids="{1 if has_kids else 0}"'
            f' data-sort-name="{esc(child.name)}"'
            f' data-size="{child.size}" data-files="{child.file_count}"'
            f' data-dirs="{child.dir_count}" data-kind="{0 if is_dir else 1}"'
            f' data-pct="{pct:.6f}"{viz_idx_attr}{hidden_attr}>'
            f'{idx_cell}'
            f'<td class="name" style="padding-left:{indent_rem:.2f}rem">{name_inner}</td>'
            f'<td class="share-cell">'
            f'<div class="share-bar" title="{pct:.1f}%">'
            f'<span style="width:{min(100.0, pct):.4f}%;background:{bar_color}"></span></div>'
            f'<span class="share-pct">{pct:.1f}%</span></td>'
            f'<td class="num size">{size_pill}</td>'
            f'<td class="num">{files_pill}</td>'
            f'<td class="num">{dirs_pill}</td>'
            f'</tr>'
        )

        if has_kids:
            rows.extend(
                _html_tree_rows(
                    child,
                    esc,
                    limit,
                    max_depth,
                    path_id=child_path,
                    depth=depth + 1,
                    share_base=max(child.size, 1),
                    color_offset=color_offset + i + 1,
                )
            )

    return rows


def render_report_html(
    dir_info: DirInfo,
    target_path: Path,
    *,
    tree_view: bool,
    limit: int,
) -> str:
    """HTML5 interactive report: storage chart, sortable table, expandable tree (dark theme)."""
    _ = tree_view
    esc = html.escape
    path_s = str(target_path)
    title_esc = esc(f"Disk usage - {path_s}")
    gen = esc(datetime.now().isoformat(timespec="seconds"))
    size_h = esc(format_size(dir_info.size))
    total_sz = max(dir_info.size, 1)

    viz_html = _html_storage_viz_block(dir_info, esc, limit)

    rows = _html_tree_rows(
        dir_info,
        esc,
        limit,
        28,
        path_id="",
        depth=0,
        share_base=total_sz,
        color_offset=0,
    )
    table_body = (
        "<tbody>" + "".join(rows) + "</tbody>"
        if rows
        else '<tbody><tr><td colspan="6" class="empty">No items</td></tr></tbody>'
    )

    root_line = (
        f'<div class="tree-root-label"><strong>{esc(dir_info.name)}</strong> '
        f'<span class="tree-meta">{esc(format_size(dir_info.size))}</span></div>'
    )
    # One flat <table> + <colgroup> gives consistent column widths at every
    # depth (fixes the "columns misalign in subfolders" problem entirely).
    colgroup = (
        '<colgroup>'
        '<col class="col-w-idx">'
        '<col class="col-w-name">'
        '<col class="col-w-share">'
        '<col class="col-w-size">'
        '<col class="col-w-files">'
        '<col class="col-w-dirs">'
        '</colgroup>'
    )
    # Icons for toolbar chrome + column headers. Keeping the templating
    # inline would double the column-header line length; a single helper
    # keeps it DRY and makes the markup easy to scan.
    def _th(key: str, label: str, icon: str, *, extra: str = "") -> str:
        cls = "sortable" + ((" " + extra) if extra else "")
        return (
            f'<th class="{cls}" data-sort-key="{key}" scope="col">'
            f'<span class="th-inner">'
            f'<span class="th-icon">{_icon(icon, size=12, cls="chrome-icon")}</span>'
            f'{label}</span></th>'
        )

    def _btn_label(icon: str, text: str) -> str:
        return f'<span class="btn-icon">{_icon(icon, size=13, cls="chrome-icon")}</span>{text}'

    table_section = (
        '<section class="panel" id="pytree-table-panel">'
        "<h2>Contents</h2>"
        '<p class="table-hint">'
        "Click column headers to sort <strong>top-level</strong> items (share = % of total scan). "
        "Click the caret next to a folder to open it; nested <strong>Share</strong> is % of that folder."
        "</p>"
        '<div class="tree-toolbar">'
        '<div class="tree-filter-wrap">'
        f'<span class="tree-filter-icon">{_icon("search", size=14, cls="chrome-icon")}</span>'
        '<input type="search" id="tree-filter" class="tree-filter" '
        'placeholder="Filter top-level by name..." autocomplete="off" spellcheck="false" />'
        '</div>'
        '<label class="toolbar-toggle" title="Always show folders before files when sorting">'
        '<input type="checkbox" id="folders-first-cb">'
        f'<span class="btn-icon">{_icon("folder_up", size=13, cls="chrome-icon")}</span>'
        'Folders first'
        '</label>'
        f'<button type="button" class="btn" id="tree-expand-all">{_btn_label("expand_all", "Expand all")}</button>'
        f'<button type="button" class="btn" id="tree-collapse-all">{_btn_label("collapse_all", "Collapse all")}</button>'
        '<span class="tree-filter-status" id="tree-filter-status"></span>'
        "</div>"
        '<div class="table-wrap merged-tree-table">'
        f"{root_line}"
        '<table id="pytree-items">'
        f"{colgroup}"
        "<thead><tr>"
        '<th class="num">#</th>'
        f'{_th("name", "Name", "label")}'
        f'{_th("pct", "Share", "pie")}'
        f'{_th("size", "Size", "disk", extra="sort-desc")}'
        f'{_th("files", "Files", "file")}'
        f'{_th("dirs", "Dirs", "dir")}'
        "</tr></thead>"
        f"{table_body}"
        "</table></div></section>"
    )

    body = (
        '<div class="layout">\n'
        '<section class="panel panel-viz"><h2>Storage overview</h2>'
        f"{viz_html}</section>\n"
        f"{table_section}\n"
        "</div>\n"
    )

    css = """\
:root {
  --bg: #0d1117;
  --bg-elevated: #161b22;
  --border: #30363d;
  --text: #e6edf3;
  --muted: #8b949e;
  --accent: #58a6ff;
  --accent-dim: #388bfd66;
  --dir: #d2a8ff;
  --file: #79c0ff;
  --radius: 10px;
  --font: ui-sans-serif, system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  --mono: ui-monospace, "Cascadia Code", "SF Mono", Consolas, monospace;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  font-family: var(--font);
  color: var(--text);
  background: radial-gradient(1200px 800px at 10% -10%, #1f2937 0%, var(--bg) 45%);
  line-height: 1.5;
}
.wrap {
  max-width: 1800px;
  margin: 0 auto;
  padding: 2rem 1.5rem 3rem;
}
@media (min-width: 1920px) {
  .wrap { max-width: 2200px; }
}
@media (min-width: 2560px) {
  .wrap { max-width: 2600px; }
}
.layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.75rem;
  align-items: start;
}
@media (min-width: 1180px) {
  .layout {
    grid-template-columns: minmax(380px, 460px) minmax(0, 1fr);
    gap: 1.75rem 2rem;
  }
  .layout .panel-viz {
    position: sticky;
    top: 1rem;
    max-height: calc(100vh - 2rem);
    overflow: auto;
  }
  .layout .panel-viz .storage-viz-top {
    grid-template-columns: 1fr;
    justify-items: center;
  }
  .layout .panel-viz .donut-wrap { max-width: 260px; }
  .layout .panel-viz .viz-charts-col { max-width: 100%; }
}
header.hero {
  margin-bottom: 1.75rem;
  padding: 1.5rem 1.25rem;
  background: linear-gradient(135deg, var(--bg-elevated) 0%, #1c2128 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 8px 32px rgba(0,0,0,.35);
}
header.hero h1 {
  margin: 0 0 0.75rem;
  font-size: 1.35rem;
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--text);
}
.meta {
  display: grid;
  gap: 0.35rem 1.5rem;
  grid-template-columns: auto 1fr;
  font-size: 0.9rem;
}
.meta dt {
  margin: 0;
  color: var(--muted);
  font-weight: 500;
}
.meta dd {
  margin: 0;
  font-variant-numeric: tabular-nums;
}
.meta code {
  font-family: var(--mono);
  font-size: 0.85em;
  padding: 0.15rem 0.4rem;
  background: var(--bg);
  border-radius: 4px;
  border: 1px solid var(--border);
  word-break: break-all;
}
.stat-big {
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--accent);
}
.panel {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1.25rem 1.25rem 1.5rem;
  box-shadow: 0 4px 24px rgba(0,0,0,.25);
}
.panel h2 {
  margin: 0 0 1rem;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text);
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
thead th {
  text-align: left;
  padding: 0.65rem 0.75rem;
  color: var(--muted);
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--border);
}
thead th:nth-child(4),
thead th:nth-child(5),
thead th:nth-child(6) { text-align: right; }
/* Fixed layout + <colgroup> widths keep columns aligned at every depth. */
#pytree-items { table-layout: fixed; width: 100%; }
#pytree-items .col-w-idx   { width: 3rem; }
#pytree-items .col-w-share { width: 12rem; }
#pytree-items .col-w-size  { width: 7rem; }
#pytree-items .col-w-files { width: 7rem; }
#pytree-items .col-w-dirs  { width: 6rem; }
/* col-w-name is intentionally unset so it takes the remaining width. */
.heat-pill {
  display: inline-block;
  padding: 0.12rem 0.55rem;
  border-radius: 999px;
  min-width: 2.5rem;
  text-align: right;
  font-family: var(--mono);
  font-size: 0.82rem;
  font-variant-numeric: tabular-nums;
  color: #f6f8fa;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.55);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
  white-space: nowrap;
}
/* Structural zero: keep the same pill silhouette but mute it so rows align
   visually and we never leave a bare number in an otherwise pill column. */
.heat-pill-zero {
  background: #1b2029;
  color: var(--muted);
  text-shadow: none;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.04);
}
.tree-root-label {
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
  font-size: 0.95rem;
}
thead th.sortable {
  cursor: pointer;
  user-select: none;
  transition: color 0.12s ease, background 0.12s ease;
}
thead th.sortable:hover { color: var(--accent); background: #1c2128; }
thead th.sort-asc::after { content: " \\25B2"; font-size: 0.65em; opacity: 0.85; }
thead th.sort-desc::after { content: " \\25BC"; font-size: 0.65em; opacity: 0.85; }
/* Column header = [icon] label; inline-flex keeps both baselines aligned and
   lets the sort glyph ("::after") hug the label on the right. */
thead th .th-inner {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
thead th .th-icon { color: var(--muted); display: inline-flex; }
thead th.sortable:hover .th-icon { color: var(--accent); }
.panel-viz h2, .panel-tree h2 { margin-top: 0; }
.table-hint, .tree-hint {
  margin: 0 0 1rem;
  font-size: 0.82rem;
  color: var(--muted);
}
#pytree-viz-data { display: none; }
.storage-viz {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.viz-toolbar-wrap { width: 100%; }
.storage-viz-top {
  display: grid;
  grid-template-columns: minmax(200px, 280px) minmax(0, 1fr);
  gap: 1.25rem 1.75rem;
  align-items: start;
}
@media (max-width: 900px) {
  .storage-viz-top {
    grid-template-columns: 1fr;
    justify-items: center;
  }
  .viz-charts-col { width: 100%; max-width: 100%; }
}
.donut-wrap { justify-self: center; width: 100%; max-width: 280px; }
.donut-svg { width: 100%; max-width: 280px; height: auto; display: block; filter: drop-shadow(0 4px 12px rgba(0,0,0,.4)); }
.viz-charts-col {
  width: 100%;
  min-width: 0;
}
.viz-title {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.stacked-hbar {
  display: flex;
  height: 24px;
  border-radius: 12px;
  overflow: hidden;
  background: #21262d;
  margin-bottom: 0;
  box-shadow: inset 0 1px 3px rgba(0,0,0,.35);
}
.stacked-hbar > span {
  display: block;
  height: 100%;
  min-width: 0;
  transition: opacity 0.15s ease;
}
.stacked-hbar > span:hover { opacity: 0.92; }
.viz-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  margin-bottom: 0.85rem;
}
.viz-toolbar .viz-tb-btn { font-size: 0.8rem; padding: 0.3rem 0.65rem; }
.viz-status { font-size: 0.8rem; color: var(--muted); }
.viz-tooltip {
  position: fixed;
  z-index: 2000;
  pointer-events: none;
  max-width: 300px;
  padding: 0.65rem 0.85rem;
  background: #21262d;
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 10px 40px rgba(0,0,0,.55);
  font-size: 0.82rem;
  line-height: 1.45;
  color: var(--text);
}
.viz-tooltip strong { color: var(--accent); font-size: 0.95em; }
.viz-tooltip em { color: var(--muted); font-size: 0.9em; }
.viz-donut-seg, .viz-hbar-seg {
  cursor: pointer;
  transition: opacity 0.12s ease, filter 0.12s ease;
}
.viz-donut-seg:hover, .viz-hbar-seg:hover { filter: brightness(1.12); }
.viz-donut-seg:focus { outline: 2px solid var(--accent); outline-offset: 2px; }
.viz-donut-empty {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  color: var(--muted);
  text-align: center;
}
.legend-col {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.legend-col-full {
  width: 100%;
  max-height: none;
  overflow: visible;
  padding-top: 0.25rem;
  border-top: 1px solid var(--border);
}
.legend-row, .viz-legend-row {
  display: grid;
  grid-template-columns: auto 14px minmax(120px, 1fr) auto auto;
  gap: 0.5rem 0.85rem;
  align-items: start;
  font-size: 0.85rem;
}
.viz-legend-row {
  cursor: pointer;
  border-radius: 6px;
  padding: 0.15rem 0.25rem;
  margin: 0 -0.25rem;
  transition: background 0.12s ease;
}
.viz-legend-row:hover { background: #21262d; }
.viz-legend-row:has(.viz-filter-cb:not(:checked)) { opacity: 0.65; }
.viz-filter-cb { cursor: pointer; accent-color: var(--accent); }
.legend-row .swatch {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  border: 1px solid rgba(255,255,255,.12);
}
.legend-name {
  overflow: visible;
  white-space: normal;
  word-break: break-word;
  line-height: 1.35;
  min-width: 0;
}
.legend-pct { color: var(--muted); font-variant-numeric: tabular-nums; }
.legend-sz { font-variant-numeric: tabular-nums; color: var(--text); }
.viz-empty { margin: 0; color: var(--muted); }
td.share-cell { vertical-align: middle; }
.share-bar {
  height: 8px;
  background: #21262d;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.25rem;
  max-width: 140px;
}
.share-bar span { display: block; height: 100%; border-radius: 4px; min-width: 2px; }
.share-pct { font-size: 0.75rem; color: var(--muted); font-variant-numeric: tabular-nums; }
.tree-toolbar {
  margin-bottom: 0.75rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}
/* Search input with a leading magnifier icon. The wrapper owns the flex
   sizing; the input itself just fills 100% of it. */
.tree-filter-wrap {
  position: relative;
  flex: 1 1 220px;
  min-width: 180px;
  max-width: 360px;
  display: flex;
  align-items: center;
}
.tree-filter-icon {
  position: absolute;
  left: 0.6rem;
  display: inline-flex;
  color: var(--muted);
  pointer-events: none;
}
.tree-filter {
  width: 100%;
  font: inherit;
  font-size: 0.85rem;
  padding: 0.4rem 0.75rem 0.4rem 2rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  outline: none;
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}
.tree-filter::placeholder { color: var(--muted); }
.tree-filter:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-dim); }
.tree-filter-wrap:focus-within .tree-filter-icon { color: var(--accent); }
.tree-filter-status { font-size: 0.8rem; color: var(--muted); margin-left: auto; }
.toolbar-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: var(--muted);
  cursor: pointer;
  user-select: none;
  padding: 0.25rem 0.5rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: #21262d;
  transition: color 0.12s ease, border-color 0.12s ease;
}
.toolbar-toggle:hover { color: var(--text); border-color: var(--accent); }
.toolbar-toggle input { accent-color: var(--accent); cursor: pointer; }
.toolbar-toggle:has(input:checked) { color: var(--text); border-color: var(--accent); }
.item-row.viz-highlight > td {
  background: rgba(88, 166, 255, 0.14);
  box-shadow: inset 3px 0 0 var(--accent);
}
.item-row.row-hidden { display: none; }
.btn {
  font: inherit;
  font-size: 0.85rem;
  padding: 0.35rem 0.85rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: #21262d;
  color: var(--text);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}
.btn:hover { background: #30363d; border-color: var(--accent); }
/* Shared icon conventions for toolbar/button/header chrome. All `.chrome-icon`
   SVGs inherit color via `fill="currentColor"` so hover/focus states just
   update the parent's color. */
.chrome-icon { display: block; flex-shrink: 0; }
.btn-icon { display: inline-flex; align-items: center; color: var(--muted); }
.btn:hover .btn-icon,
.toolbar-toggle:hover .btn-icon,
.toolbar-toggle:has(input:checked) .btn-icon { color: var(--accent); }
.merged-tree-table {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem;
  background: var(--bg-elevated);
  max-height: min(85vh, 1200px);
  overflow: auto;
}
.merged-tree-table table { border-collapse: collapse; }
/* Expand caret + placeholder share the same box so the icon and name
   always land at exactly the same x-offset whether or not the row is a
   folder that can be opened. */
.row-expand,
.row-expand-placeholder {
  display: inline-block;
  width: 1.2rem;
  height: 1.2rem;
  margin-right: 0.35rem;
  vertical-align: middle;
}
.row-expand {
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: #21262d;
  color: var(--text);
  cursor: pointer;
  font-size: 0.55rem;
  line-height: 1.1;
}
.row-expand::before {
  content: "\\25B6";
  display: inline-block;
  transition: transform 0.15s ease;
}
.row-expand[aria-expanded="true"]::before { transform: rotate(90deg); }
.row-expand:hover { background: #30363d; border-color: var(--accent); }
.entry-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.25rem;
  margin-right: 0.4rem;
  vertical-align: middle;
  line-height: 0;
}
.entry-icon[data-kind="dir"]  { color: var(--dir); }
.entry-icon[data-kind="file"] { color: var(--file); }
.entry-icon .icon-svg { display: block; }
.tree-meta { color: var(--muted); font-weight: normal; }
.item-row {
  border-bottom: 1px solid #21262d;
  transition: background 0.12s ease;
}
.item-row:hover { background: #1f242c; }
tbody td {
  padding: 0.45rem 0.75rem;
  vertical-align: middle;
}
tbody td.num { text-align: right; font-variant-numeric: tabular-nums; }
tbody td.name {
  word-break: break-word;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
tbody td.empty {
  text-align: center;
  color: var(--muted);
  padding: 1.5rem;
}
pre.tree {
  margin: 0;
  padding: 1rem 1.1rem;
  font-family: var(--mono);
  font-size: 0.82rem;
  line-height: 1.45;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: auto;
  color: #c9d1d9;
}
footer {
  margin-top: 2rem;
  text-align: center;
  font-size: 0.8rem;
  color: var(--muted);
}
"""

    summary = (
        "<header class=\"hero\">\n"
        f"<h1>{title_esc}</h1>\n"
        '<dl class="meta">\n'
        f"<dt>Path</dt><dd><code>{esc(path_s)}</code></dd>\n"
        f"<dt>Generated</dt><dd>{gen}</dd>\n"
        f"<dt>Total size</dt><dd class=\"stat-big\">{size_h}</dd>\n"
        f"<dt>Contents</dt><dd>{format_count(dir_info.file_count)} files &middot; "
        f"{format_count(dir_info.dir_count)} directories</dd>\n"
        "</dl>\n</header>\n"
    )

    script = """
<script>
(function () {
  var table = document.getElementById("pytree-items");
  if (!table) return;
  var tbody = table.querySelector("tbody");
  if (!tbody) return;

  // ---------- Build an index of the flat row list ----------
  // Every row is a direct child of <tbody>; parent-child relationships live
  // on data-path / data-parent. We index once and reuse for sort / expand /
  // filter so we never re-query the DOM.
  var rows = Array.prototype.slice.call(tbody.querySelectorAll(":scope > tr.item-row"));
  var byPath = Object.create(null);
  var childrenOf = Object.create(null);
  var topRows = [];
  rows.forEach(function (r) {
    var p = r.getAttribute("data-path");
    var par = r.getAttribute("data-parent") || "";
    byPath[p] = r;
    (childrenOf[par] = childrenOf[par] || []).push(r);
    if (!par) topRows.push(r);
  });

  // ---------- Expand / collapse ----------
  function directChildren(row) {
    return childrenOf[row.getAttribute("data-path")] || [];
  }
  function setExpanded(row, open) {
    var btn = row.querySelector(".row-expand");
    if (!btn) return;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) {
      directChildren(row).forEach(function (ch) { ch.hidden = false; });
    } else {
      // Recursively hide and collapse every descendant.
      var stack = directChildren(row).slice();
      while (stack.length) {
        var r = stack.pop();
        r.hidden = true;
        var b = r.querySelector(".row-expand");
        if (b) b.setAttribute("aria-expanded", "false");
        Array.prototype.push.apply(stack, directChildren(r));
      }
    }
  }

  table.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".row-expand");
    if (!btn || !table.contains(btn)) return;
    var row = btn.closest("tr.item-row");
    if (!row) return;
    var open = btn.getAttribute("aria-expanded") !== "true";
    setExpanded(row, open);
  });

  // ---------- Sorting ----------
  var headers = table.querySelectorAll("thead th[data-sort-key]");
  var current = { key: "size", dir: "desc" };
  var foldersFirstCb = document.getElementById("folders-first-cb");

  function clearSortMarks() {
    headers.forEach(function (th) { th.classList.remove("sort-asc", "sort-desc"); });
  }

  function cmp(a, b, key, dir) {
    if (foldersFirstCb && foldersFirstCb.checked) {
      var ka = parseInt(a.getAttribute("data-kind") || "0", 10);
      var kb = parseInt(b.getAttribute("data-kind") || "0", 10);
      if (ka !== kb) return ka - kb; // 0 = dir, 1 = file → dirs first
    }
    var mul = dir === "asc" ? 1 : -1;
    if (key === "name") {
      var na = a.getAttribute("data-sort-name") || "";
      var nb = b.getAttribute("data-sort-name") || "";
      if (na !== nb) {
        return mul * na.localeCompare(nb, undefined, { numeric: true, sensitivity: "base" });
      }
    } else {
      var ak = key === "pct" ? "data-pct" : "data-" + key;
      var va = parseFloat(a.getAttribute(ak) || "0");
      var vb = parseFloat(b.getAttribute(ak) || "0");
      if (va !== vb) return mul * (va - vb);
    }
    var fa = a.getAttribute("data-sort-name") || "";
    var fb = b.getAttribute("data-sort-name") || "";
    return fa.localeCompare(fb, undefined, { numeric: true, sensitivity: "base" });
  }

  // Return every descendant of `row` in depth-first document order, so that
  // when we reorder top-level rows their whole subtree moves with them.
  function subtree(row) {
    var out = [];
    var stack = directChildren(row).slice().reverse();
    while (stack.length) {
      var r = stack.pop();
      out.push(r);
      var kids = directChildren(r);
      for (var i = kids.length - 1; i >= 0; i--) stack.push(kids[i]);
    }
    return out;
  }

  function applySort(key, toggle) {
    if (toggle) {
      if (current.key === key) {
        current.dir = current.dir === "asc" ? "desc" : "asc";
      } else {
        current.key = key;
        current.dir = key === "name" ? "asc" : "desc";
      }
    }
    clearSortMarks();
    var th = table.querySelector('thead th[data-sort-key="' + current.key + '"]');
    if (th) th.classList.add(current.dir === "asc" ? "sort-asc" : "sort-desc");

    var sorted = topRows.slice().sort(function (a, b) {
      return cmp(a, b, current.key, current.dir);
    });
    var frag = document.createDocumentFragment();
    sorted.forEach(function (row, i) {
      var idx = row.querySelector(".col-idx");
      if (idx) idx.textContent = String(i + 1);
      frag.appendChild(row);
      subtree(row).forEach(function (r) { frag.appendChild(r); });
    });
    tbody.appendChild(frag);
  }

  headers.forEach(function (th) {
    th.addEventListener("click", function () {
      applySort(th.getAttribute("data-sort-key"), true);
    });
  });
  if (foldersFirstCb) {
    foldersFirstCb.addEventListener("change", function () { applySort(current.key, false); });
  }
  applySort("size", false);

  // ---------- Expand-all / Collapse-all ----------
  var expandBtn = document.getElementById("tree-expand-all");
  var collapseBtn = document.getElementById("tree-collapse-all");
  if (expandBtn) {
    expandBtn.addEventListener("click", function () {
      rows.forEach(function (r) {
        if (r.getAttribute("data-has-kids") === "1") {
          var b = r.querySelector(".row-expand");
          if (b) b.setAttribute("aria-expanded", "true");
        }
        if (r.getAttribute("data-depth") !== "0") r.hidden = false;
      });
    });
  }
  if (collapseBtn) {
    collapseBtn.addEventListener("click", function () {
      rows.forEach(function (r) {
        var b = r.querySelector(".row-expand");
        if (b) b.setAttribute("aria-expanded", "false");
        if (r.getAttribute("data-depth") !== "0") r.hidden = true;
      });
    });
  }

  // ---------- Filter (top-level by name) ----------
  var filterInput = document.getElementById("tree-filter");
  var filterStatus = document.getElementById("tree-filter-status");
  if (filterInput) {
    function applyFilter() {
      var q = (filterInput.value || "").trim().toLowerCase();
      var shown = 0;
      topRows.forEach(function (row) {
        var name = (row.getAttribute("data-sort-name") || "").toLowerCase();
        var match = !q || name.indexOf(q) !== -1;
        row.classList.toggle("row-hidden", !match);
        // Hide the whole subtree when filtered out; leave expansion state alone.
        subtree(row).forEach(function (r) { r.classList.toggle("row-hidden", !match); });
        if (match) shown += 1;
      });
      if (filterStatus) {
        filterStatus.textContent = q
          ? shown + " of " + topRows.length + " match"
          : "";
      }
    }
    filterInput.addEventListener("input", applyFilter);
    filterInput.addEventListener("keydown", function (e) {
      if (e.key === "Escape") { filterInput.value = ""; applyFilter(); }
    });
  }
})();
</script>
"""

    viz_script = """
<script>
(function () {
  var dataEl = document.getElementById("pytree-viz-data");
  if (!dataEl) return;
  var items = [];
  try { items = JSON.parse(dataEl.textContent || "[]"); } catch (e1) { return; }
  if (!items.length) return;

  var included = items.map(function () { return true; });
  var cx = 100, cy = 100, outerR = 78, innerR = 44;
  var pathG = document.getElementById("pytree-donut-paths");
  var hbar = document.getElementById("pytree-stacked-hbar");
  var donutEmpty = document.getElementById("pytree-donut-empty");
  var statusEl = document.getElementById("viz-filter-status");
  var tip = document.getElementById("pytree-viz-tooltip");
  var btnAll = document.getElementById("viz-show-all");
  var btnNone = document.getElementById("viz-hide-all");

  function htmlEscape(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function activeTotal() {
    var t = 0;
    items.forEach(function (it, i) { if (included[i]) t += it.size; });
    return t;
  }

  function highlightRow(idx) {
    clearRowHighlight();
    if (idx == null || isNaN(idx)) return;
    var rows = document.querySelectorAll(
      '#pytree-items tr.item-row[data-viz-idx="' + idx + '"]'
    );
    rows.forEach(function (r) { r.classList.add("viz-highlight"); });
  }
  function clearRowHighlight() {
    document
      .querySelectorAll("#pytree-items tr.item-row.viz-highlight")
      .forEach(function (r) { r.classList.remove("viz-highlight"); });
  }

  function bindSegEvents(nodes) {
    nodes.forEach(function (node) {
      node.addEventListener("mouseenter", function (e) {
        var idx = parseInt(node.getAttribute("data-viz-idx"), 10);
        showTip(e.clientX, e.clientY, idx);
        highlightRow(idx);
      });
      node.addEventListener("mousemove", function (e) {
        var idx = parseInt(node.getAttribute("data-viz-idx"), 10);
        showTip(e.clientX, e.clientY, idx);
      });
      node.addEventListener("mouseleave", function () {
        hideTip();
        clearRowHighlight();
      });
      node.addEventListener("click", function (e) {
        e.preventDefault();
        toggleIdx(parseInt(node.getAttribute("data-viz-idx"), 10));
      });
      node.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          toggleIdx(parseInt(node.getAttribute("data-viz-idx"), 10));
        }
      });
    });
  }

  function tooltipHtml(idx) {
    var it = items[idx];
    if (!it) return "";
    var tot = activeTotal();
    var pctChart = included[idx] && tot > 0 ? (100 * it.size / tot) : 0;
    var type = it.isDir ? "Directory" : "File";
    var lines = [
      "<strong>" + htmlEscape(it.name) + "</strong>",
      "Type: " + type,
      "Size: " + htmlEscape(it.human) + " (" + it.size.toLocaleString() + " bytes)",
      "Files: " + it.files + " · Dirs: " + it.dirs,
      "Of scanned folder: " + (it.pctRoot != null ? it.pctRoot.toFixed(1) : "?") + "%"
    ];
    if (included[idx] && tot > 0) {
      lines.push("Of visible chart: " + pctChart.toFixed(1) + "%");
    } else {
      lines.push("<em>Filtered out of chart</em>");
    }
    return lines.join("<br/>");
  }

  function showTip(x, y, idx) {
    if (!tip) return;
    tip.innerHTML = tooltipHtml(idx);
    tip.hidden = false;
    var tw = 300, th = tip.offsetHeight || 120;
    tip.style.left = Math.min(window.innerWidth - tw - 8, x + 12) + "px";
    tip.style.top = Math.min(window.innerHeight - th - 8, y + 12) + "px";
  }

  function hideTip() {
    if (tip) tip.hidden = true;
  }

  function buildDonutSvgPaths() {
    if (!pathG) return;
    var tot = activeTotal();
    if (tot <= 0) {
      pathG.innerHTML = "";
      return;
    }
    var start = -Math.PI / 2;
    var html = [];
    items.forEach(function (it, idx) {
      if (!included[idx] || it.size <= 0) return;
      var sweep = 2 * Math.PI * (it.size / tot);
      var a0 = start;
      var a1 = start + sweep;
      start = a1;
      var x0o = cx + outerR * Math.cos(a0), y0o = cy + outerR * Math.sin(a0);
      var x1o = cx + outerR * Math.cos(a1), y1o = cy + outerR * Math.sin(a1);
      var x0i = cx + innerR * Math.cos(a0), y0i = cy + innerR * Math.sin(a0);
      var x1i = cx + innerR * Math.cos(a1), y1i = cy + innerR * Math.sin(a1);
      var large = sweep > Math.PI ? 1 : 0;
      html.push(
        '<path class="viz-donut-seg" data-viz-idx="' + idx + '" tabindex="0" d="M ' + x0o.toFixed(2) + " " + y0o.toFixed(2) +
        " A " + outerR + " " + outerR + " 0 " + large + " 1 " + x1o.toFixed(2) + " " + y1o.toFixed(2) +
        " L " + x1i.toFixed(2) + " " + y1i.toFixed(2) +
        " A " + innerR + " " + innerR + " 0 " + large + " 0 " + x0i.toFixed(2) + " " + y0i.toFixed(2) +
        ' Z" fill="' + it.color + '" stroke="#0d1117" stroke-width="1"/>'
      );
    });
    pathG.innerHTML = html.join("");
    bindSegEvents(pathG.querySelectorAll(".viz-donut-seg"));
  }

  function buildHbar() {
    if (!hbar) return;
    var tot = activeTotal();
    hbar.innerHTML = "";
    if (tot <= 0) return;
    items.forEach(function (it, idx) {
      if (!included[idx]) return;
      var w = (100 * it.size) / tot;
      var span = document.createElement("span");
      span.className = "viz-hbar-seg";
      span.setAttribute("data-viz-idx", String(idx));
      span.style.width = w.toFixed(4) + "%";
      span.style.background = it.color;
      span.style.display = "block";
      span.style.height = "100%";
      span.style.minWidth = "2px";
      hbar.appendChild(span);
    });
    bindSegEvents(hbar.querySelectorAll(".viz-hbar-seg"));
  }

  function updateLegendPct() {
    var tot = activeTotal();
    var allOn = included.filter(Boolean).length === items.length;
    items.forEach(function (it, idx) {
      var row = document.querySelector('.viz-legend-row[data-viz-idx="' + idx + '"]');
      if (!row) return;
      var pctEl = row.querySelector(".legend-pct");
      if (!pctEl) return;
      if (included[idx] && tot > 0) {
        pctEl.textContent = ((100 * it.size) / tot).toFixed(1) + "%";
        pctEl.title = allOn
          ? "Share of scanned folder"
          : "Share of visible chart (of scan: " + it.pctRoot.toFixed(1) + "%)";
      } else {
        pctEl.textContent = it.pctRoot.toFixed(1) + "%";
        pctEl.title = "Share of scanned folder — hidden from chart";
      }
    });
  }

  function updateStatus() {
    var n = included.filter(Boolean).length;
    if (statusEl) {
      statusEl.textContent =
        n === items.length
          ? "Showing all " + items.length + " items in the chart."
          : "Showing " + n + " of " + items.length + " — donut and bar use only visible items.";
    }
    if (donutEmpty) donutEmpty.hidden = activeTotal() > 0;
    updateLegendPct();
  }

  function toggleIdx(idx) {
    if (idx < 0 || idx >= items.length) return;
    included[idx] = !included[idx];
    var cb = document.querySelector('.viz-filter-cb[data-viz-idx="' + idx + '"]');
    if (cb) cb.checked = included[idx];
    refresh();
  }

  function refresh() {
    buildDonutSvgPaths();
    buildHbar();
    updateStatus();
  }

  document.querySelectorAll(".viz-filter-cb").forEach(function (cb) {
    cb.addEventListener("change", function () {
      var idx = parseInt(cb.getAttribute("data-viz-idx"), 10);
      included[idx] = cb.checked;
      refresh();
    });
  });

  document.querySelectorAll(".viz-legend-row").forEach(function (row) {
    row.addEventListener("click", function (e) {
      if (e.target.tagName === "INPUT") return;
      var idx = parseInt(row.getAttribute("data-viz-idx"), 10);
      included[idx] = !included[idx];
      var c = row.querySelector(".viz-filter-cb");
      if (c) c.checked = included[idx];
      refresh();
    });
    row.addEventListener("mouseenter", function () {
      highlightRow(parseInt(row.getAttribute("data-viz-idx"), 10));
    });
    row.addEventListener("mouseleave", clearRowHighlight);
  });

  if (btnAll) {
    btnAll.addEventListener("click", function () {
      items.forEach(function (_, i) { included[i] = true; });
      document.querySelectorAll(".viz-filter-cb").forEach(function (cb) { cb.checked = true; });
      refresh();
    });
  }
  if (btnNone) {
    btnNone.addEventListener("click", function () {
      items.forEach(function (_, i) { included[i] = false; });
      document.querySelectorAll(".viz-filter-cb").forEach(function (cb) { cb.checked = false; });
      refresh();
    });
  }

  document.addEventListener("scroll", hideTip, true);
  window.addEventListener("blur", hideTip);

  bindSegEvents(document.querySelectorAll(".viz-donut-seg, .viz-hbar-seg"));
  updateStatus();
})();
</script>
"""

    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title_esc}</title>\n"
        f"<style>\n{css}</style>\n"
        "</head>\n<body>\n"
        '<div class="wrap">\n'
        f"{summary}{body}"
        '<footer>SizeTree / pytree disk usage report</footer>\n'
        "</div>\n"
        f"{script}{viz_script}"
        "</body>\n</html>\n"
    )


def write_scan_report(
    dir_info: DirInfo,
    target_path: Path,
    out_path: Path,
    fmt: ReportFormat,
    *,
    tree_view: bool,
    limit: int,
) -> None:
    """Write scan report to a file in the given format."""
    if fmt == ReportFormat.json:
        payload = {
            "scanned_path": str(target_path),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "root": dir_info_to_json_dict(dir_info),
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    elif fmt == ReportFormat.markdown:
        text = render_report_markdown(dir_info, target_path, tree_view=tree_view, limit=limit)
    elif fmt == ReportFormat.html:
        text = render_report_html(dir_info, target_path, tree_view=tree_view, limit=limit)
    else:
        text = render_report_text(dir_info, target_path, tree_view=tree_view, limit=limit)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")


_REPORT_EXTENSIONS: Dict[ReportFormat, str] = {
    ReportFormat.text: ".txt",
    ReportFormat.json: ".json",
    ReportFormat.markdown: ".md",
    ReportFormat.html: ".html",
}


def _slugify_for_filename(value: str) -> str:
    """Turn an arbitrary path segment into a safe temp-file slug."""
    cleaned = "".join(c if c.isalnum() or c in "-_." else "_" for c in value)
    cleaned = cleaned.strip("._") or "root"
    return cleaned[:40]


def make_temp_report_path(target_path: Path, fmt: ReportFormat) -> Path:
    """Build a stable, human-friendly temp path for a one-off report.

    Uses ``<tmp>/pytree-<slug>-<timestamp><ext>`` so repeated scans don't
    clobber each other and the file is easy to identify on disk.
    """
    slug = _slugify_for_filename(target_path.name or target_path.anchor or "root")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    ext = _REPORT_EXTENSIONS.get(fmt, ".txt")
    return Path(tempfile.gettempdir()) / f"pytree-{slug}-{stamp}{ext}"


def open_in_browser(path: Path) -> bool:
    """Open ``path`` in the user's default browser. Returns success."""
    try:
        return webbrowser.open(path.resolve().as_uri())
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────── #
#                         TUI VISUAL HELPERS                              #
# ─────────────────────────────────────────────────────────────────────── #
# Shared rendering helpers so the Textual tree, top-items sidebar, and
# info panel all speak the same visual language (heat colors, bars,
# icons, counts). Rich ``Text`` objects with inline ``style=`` are used
# everywhere so the TUI stays a single source of truth for colors.

_TUI_BAR_FILL = "█"
_TUI_BAR_EMPTY = "░"
# Column widths used for the tree rows. Padding the name to a fixed width
# makes the bar / % / size columns line up across siblings — the main
# payoff of these constants.
_TUI_TREE_BAR_WIDTH = 12
_TUI_TREE_NAME_W = 26
_TUI_TREE_SIZE_W = 10
_TUI_TREE_PCT_W = 5   # "100.0" fits; rendered as " 99.9%" via >5.1f + %
_TUI_TREE_COUNT_W = 14  # "9,999,999f 999d" range

# Top-items sidebar is narrow (1fr of the split) so columns are tighter.
_TUI_TOP_BAR_WIDTH = 14
_TUI_TOP_NAME_W = 18
_TUI_TOP_SIZE_W = 9

# Colors are kept consistent with the HTML report for a coherent look.
_TUI_COLOR_DIR = "#d2a8ff"
_TUI_COLOR_FILE = "#79c0ff"
_TUI_COLOR_ACCENT = "#58a6ff"
_TUI_COLOR_GOOD = "#3fb950"
_TUI_COLOR_WARN = "#d4a72c"
_TUI_COLOR_ERR = "#f85149"
_TUI_COLOR_MUTED = "grey66"
_TUI_COLOR_DIM = "grey50"

_TUI_ICON_DIR = "📁"
_TUI_ICON_FILE = "📄"


def _tui_heat_color(ratio: float) -> str:
    """Heat-mapped RGB color string (green → yellow → red) for a 0..1 ratio.

    Matches the HTML report's perceptual sqrt curve so the TUI and the
    generated HTML feel like the same product at a glance."""
    if ratio <= 0:
        return _TUI_COLOR_DIM
    ratio = 1.0 if ratio > 1 else ratio
    curved = ratio ** 0.5
    hue = 120.0 * (1.0 - curved)  # 120=green, 60=yellow, 0=red
    lightness = 0.60
    saturation = 0.75
    r, g, b = colorsys.hls_to_rgb(hue / 360.0, lightness, saturation)
    return f"rgb({int(r * 255)},{int(g * 255)},{int(b * 255)})"


def _tui_bar(pct: float, width: int) -> str:
    """Unicode block-char progress bar."""
    pct = 0.0 if pct < 0 else (100.0 if pct > 100 else pct)
    filled = int(round(width * pct / 100.0))
    return _TUI_BAR_FILL * filled + _TUI_BAR_EMPTY * (width - filled)


def _tui_fixed_name(name: str, width: int) -> str:
    """Truncate with an ellipsis and right-pad to ``width`` cells.

    Approximates display width by code-point length, which is fine for
    filesystem paths (~always ASCII/BMP). If a path contains wide chars
    the row may drift by a cell or two — acceptable vs. bringing in a
    heavy width-aware library."""
    if len(name) > width:
        name = name[: width - 1] + "…"
    return name.ljust(width)


def _tui_counts_fragment(info: DirInfo) -> Optional[Text]:
    """Styled ``Nf  Md`` counts fragment, or ``None`` when both are zero.

    Returned as an independent Text so the caller can pad / align it."""
    if not info.file_count and not info.dir_count:
        return None
    t = Text()
    if info.file_count:
        t.append(f"{info.file_count:,}f", style=_TUI_COLOR_FILE)
    if info.file_count and info.dir_count:
        t.append(" ")
    if info.dir_count:
        t.append(f"{info.dir_count:,}d", style=_TUI_COLOR_DIR)
    return t


def _tui_name_style(is_dir: bool) -> str:
    return f"bold {_TUI_COLOR_DIR}" if is_dir else _TUI_COLOR_FILE


def _tui_entry_icon(is_dir: bool) -> str:
    return _TUI_ICON_DIR if is_dir else _TUI_ICON_FILE


def _tui_tree_label(info: DirInfo, max_size: int, parent_size: int) -> Text:
    """Rich Text label for an in-tree row.

    Fixed-width columns so rows line up across siblings:

        ICON  NAME(26)  BAR(12)  PCT(6)  SIZE(10)  COUNTS(14)  [error]

    Heat color for bar + size is based on ``size / max_size`` of the
    siblings (biggest child in a folder is always the reddest).
    """
    is_dir = entry_is_directory(info)
    ratio = (info.size / max_size) if max_size > 0 else 0.0
    color = _tui_heat_color(ratio)
    pct = (100.0 * info.size / parent_size) if parent_size > 0 else 0.0

    t = Text(no_wrap=True, overflow="ellipsis")
    t.append(f"{_tui_entry_icon(is_dir)} ")
    t.append(_tui_fixed_name(info.name, _TUI_TREE_NAME_W), style=_tui_name_style(is_dir))
    t.append(" ")
    t.append(_tui_bar(pct, _TUI_TREE_BAR_WIDTH), style=color)
    t.append(f" {pct:>{_TUI_TREE_PCT_W}.1f}%", style=_TUI_COLOR_MUTED)
    t.append(f"  {format_size(info.size):>{_TUI_TREE_SIZE_W}}", style=f"bold {color}")
    counts = _tui_counts_fragment(info)
    t.append("  ")
    if counts is not None:
        # Right-pad the counts fragment to a fixed width so the error
        # marker (when present) always lands in the same column.
        t.append_text(counts)
        pad = _TUI_TREE_COUNT_W - counts.cell_len
        if pad > 0:
            t.append(" " * pad)
    else:
        t.append(" " * _TUI_TREE_COUNT_W)
    if info.error:
        t.append(f"⚠ {info.error}", style=f"bold {_TUI_COLOR_ERR}")
    return t


def _tui_root_label(info: DirInfo) -> Text:
    """Distinct label for the tree root — no bar (it's always 100%)."""
    t = Text(overflow="ellipsis", no_wrap=True)
    t.append("💾 ")
    t.append(info.name or str(info.path), style=f"bold {_TUI_COLOR_ACCENT}")
    t.append(f"  {format_size(info.size)}", style=f"bold {_TUI_COLOR_GOOD}")
    if info.file_count or info.dir_count:
        t.append("  ")
        t.append(f"{info.file_count:,}", style=_TUI_COLOR_FILE)
        t.append(" files · ", style=_TUI_COLOR_MUTED)
        t.append(f"{info.dir_count:,}", style=_TUI_COLOR_DIR)
        t.append(" dirs", style=_TUI_COLOR_MUTED)
    if info.error:
        t.append(f"  ⚠ {info.error}", style=f"bold {_TUI_COLOR_ERR}")
    return t


def _tui_summary_text(dir_info: DirInfo) -> Text:
    """One-line richly styled scan summary for the info panel."""
    t = Text()
    t.append("💾 ", style="")
    t.append("Total ", style=_TUI_COLOR_MUTED)
    t.append(format_size(dir_info.size), style=f"bold {_TUI_COLOR_GOOD}")
    t.append("   " + _TUI_ICON_FILE + " ")
    t.append(f"{dir_info.file_count:,}", style=f"bold {_TUI_COLOR_FILE}")
    t.append(" files", style=_TUI_COLOR_MUTED)
    t.append("   " + _TUI_ICON_DIR + " ")
    t.append(f"{dir_info.dir_count:,}", style=f"bold {_TUI_COLOR_DIR}")
    t.append(" dirs", style=_TUI_COLOR_MUTED)
    return t


def _tui_scan_progress_text(files: int, dirs: int, size: int) -> Text:
    """Live in-progress counters shown while scanning."""
    t = Text()
    t.append("⟳ Scanning… ", style=f"italic {_TUI_COLOR_WARN}")
    t.append(f"{files:,}", style=f"bold {_TUI_COLOR_FILE}")
    t.append(" files · ", style=_TUI_COLOR_MUTED)
    t.append(f"{dirs:,}", style=f"bold {_TUI_COLOR_DIR}")
    t.append(" dirs · ", style=_TUI_COLOR_MUTED)
    t.append(format_size(size), style=f"bold {_TUI_COLOR_GOOD}")
    return t


def _tui_top_items_text(dir_info: DirInfo, limit: int = 20) -> Text:
    """Rich Text block for the sidebar: top-N children as horizontal bars.

    Fixed-width layout so everything aligns column-to-column:

        NN. ICON NAME(18) BAR(14) PCT(6)  SIZE(9)

    Bar width is scaled against the largest sibling so the biggest item
    always fills the row; percent is of the parent folder total.
    """
    t = Text(no_wrap=True, overflow="ellipsis")
    t.append("Top items by size", style=f"bold {_TUI_COLOR_ACCENT} underline")
    t.append("\n\n")

    kids = dir_info.children[:limit]
    if not kids:
        t.append("(empty)", style=_TUI_COLOR_MUTED)
        return t

    total = dir_info.size or 1
    max_size = max((c.size for c in kids), default=1) or 1
    rank_w = max(2, len(str(len(kids))))

    for i, ch in enumerate(kids, 1):
        is_dir = entry_is_directory(ch)
        ratio = ch.size / max_size
        color = _tui_heat_color(ratio)
        pct = 100.0 * ch.size / total
        bar = _tui_bar(100.0 * ratio, _TUI_TOP_BAR_WIDTH)

        t.append(f"{i:>{rank_w}}. ", style=_TUI_COLOR_DIM)
        t.append(f"{_tui_entry_icon(is_dir)} ")
        t.append(_tui_fixed_name(ch.name, _TUI_TOP_NAME_W), style=_tui_name_style(is_dir))
        t.append(" ")
        t.append(bar, style=color)
        t.append(f" {pct:>5.1f}%", style=_TUI_COLOR_MUTED)
        t.append(f"  {format_size(ch.size):>{_TUI_TOP_SIZE_W}}\n", style=f"bold {color}")

    return t


def _tui_legend_text() -> Text:
    """Small legend explaining the bar/heat color scheme in the footer area."""
    t = Text()
    t.append("  Heat: ", style=_TUI_COLOR_MUTED)
    for r in (0.05, 0.25, 0.5, 0.75, 1.0):
        t.append(_TUI_BAR_FILL * 2, style=_tui_heat_color(r))
    t.append("   " + _TUI_ICON_DIR + " ", style="")
    t.append("dir", style=f"bold {_TUI_COLOR_DIR}")
    t.append("   " + _TUI_ICON_FILE + " ", style="")
    t.append("file", style=_TUI_COLOR_FILE)
    return t


# ─────────────────────────────────────────────────────────────────────── #
#                              TEXTUAL TUI APP                            #
# ─────────────────────────────────────────────────────────────────────── #

class SizeTreeApp(App):
    """Textual TUI for TreeSize-like functionality.

    Layout:

    ┌─ Header ───────────────────────────────────────────────────┐
    │ info-panel: path + live scan summary + status line         │
    ├─ main-container (horizontal) ──────────────────────────────┤
    │ tree-container (2fr)      │  top-panel (1fr)               │
    │  colored, barred tree     │  Top-N horizontal bar chart    │
    ├─ Footer ───────────────────────────────────────────────────┤
    """

    CSS = """
    Screen { background: #0d1117; }

    Header { background: #161b22; color: #e6edf3; }
    Footer { background: #161b22; color: #8b949e; }

    #info-panel {
        dock: top;
        height: 7;
        background: #161b22;
        border: heavy #58a6ff;
        padding: 0 1;
    }
    #info-panel Label {
        padding: 0;
        height: 1;
    }
    #info-path { color: #58a6ff; text-style: bold; }
    #info-legend { color: #8b949e; }
    #info-status { color: #8b949e; }

    #main-container {
        height: 1fr;
        layout: horizontal;
    }

    #tree-container {
        width: 2fr;
        border: round #30363d;
        background: #0d1117;
        padding: 0 1;
    }
    #tree-container:focus-within { border: round #58a6ff; }

    #top-panel {
        width: 1fr;
        min-width: 64;
        border: round #30363d;
        background: #0d1117;
        padding: 0 1;
    }

    #top-panel-content {
        width: 1fr;
        padding: 0;
    }

    Tree {
        scrollbar-gutter: stable;
        background: #0d1117;
    }

    Tree > .tree--cursor {
        background: #1f6feb 35%;
        color: #e6edf3;
        text-style: bold;
    }
    Tree > .tree--highlight-line {
        background: #161b22;
    }
    Tree > .tree--guides {
        color: #30363d;
    }
    Tree > .tree--guides-hover,
    Tree > .tree--guides-selected {
        color: #58a6ff;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "rescan", "Rescan"),
        Binding("h", "toggle_hidden", "Hidden"),
        Binding("e", "expand_all", "Expand all"),
        Binding("c", "collapse_all", "Collapse all"),
    ]

    # Max siblings per tree node — high enough to be useful, low enough
    # not to drown the TUI when a folder has tens of thousands of files.
    _TUI_MAX_CHILDREN = 25

    def __init__(self, root_path: Path, max_depth: Optional[int] = None):
        super().__init__()
        self.root_path = root_path
        self.max_depth = max_depth
        self.dir_info: Optional[DirInfo] = None
        self.show_hidden = False
        self._last_progress_update = 0.0
        self.title = "pytree · SizeTree"
        self.sub_title = str(root_path)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="info-panel"):
            path_label = Label("", id="info-path")
            yield path_label
            yield Label("Preparing scan…", id="info-summary")
            yield Label("", id="info-status")
            yield Label("", id="info-legend")

        with Horizontal(id="main-container"):
            with Container(id="tree-container"):
                yield Tree(str(self.root_path), id="size-tree")
            with VerticalScroll(id="top-panel"):
                yield Static("", id="top-panel-content")

        yield Footer()

    async def on_mount(self) -> None:
        path_text = Text()
        path_text.append("📂 ", style="")
        path_text.append(str(self.root_path), style=f"bold {_TUI_COLOR_ACCENT}")
        self.query_one("#info-path", Label).update(path_text)
        self.query_one("#info-legend", Label).update(_tui_legend_text())

        tree = self.query_one("#size-tree", Tree)
        tree.show_root = True
        tree.guide_depth = 3

        self._start_scan()

    def _start_scan(self) -> None:
        """Kick off a scan in a worker thread so the UI stays responsive."""
        self.query_one("#info-summary", Label).update(
            _tui_scan_progress_text(0, 0, 0)
        )
        self.query_one("#info-status", Label).update(
            Text("Starting…", style=f"italic {_TUI_COLOR_MUTED}")
        )
        self.run_worker(self._scan_worker, thread=True, exclusive=True)

    def _scan_worker(self) -> None:
        """Runs on a worker thread. UI updates go through call_from_thread."""
        stats = ScanStats()
        state = {"last": 0.0}

        def cb(s: ScanStats) -> None:
            now = time.monotonic()
            if now - state["last"] < 0.12:
                return
            state["last"] = now
            current = s.current
            if len(current) > 80:
                current = "…" + current[-79:]
            self.call_from_thread(
                self._update_scan_progress, s.files, s.dirs, s.size, current
            )

        info = scan_directory(
            self.root_path, self.max_depth, stats=stats, progress_cb=cb
        )
        self.dir_info = info
        self.call_from_thread(self._finalize_scan)

    def _update_scan_progress(
        self, files: int, dirs: int, size: int, current: str
    ) -> None:
        self.query_one("#info-summary", Label).update(
            _tui_scan_progress_text(files, dirs, size)
        )
        self.query_one("#info-status", Label).update(
            Text(current, style=_TUI_COLOR_DIM)
        )

    def _finalize_scan(self) -> None:
        info = self.dir_info
        if info is None:
            return
        self.query_one("#info-summary", Label).update(_tui_summary_text(info))
        self.query_one("#info-status", Label).update(
            Text("Ready · [q]uit [r]escan [h]idden [e]xpand [c]ollapse",
                 style=_TUI_COLOR_MUTED)
        )
        self._populate_ui()

    def _visible_children(self, info: DirInfo) -> List[DirInfo]:
        kids = info.children
        if not self.show_hidden:
            kids = [c for c in kids if not c.name.startswith(".")]
        return kids[: self._TUI_MAX_CHILDREN]

    def _populate_ui(self) -> None:
        info = self.dir_info
        if info is None:
            return
        tree = self.query_one("#size-tree", Tree)
        tree.clear()
        tree.root.set_label(_tui_root_label(info))
        self._populate_tree_node(tree.root, info)
        tree.root.expand()

        top = self.query_one("#top-panel-content", Static)
        top.update(_tui_top_items_text(info, limit=20))

    def _populate_tree_node(self, node, dir_info: DirInfo) -> None:
        kids = self._visible_children(dir_info)
        max_size = max((c.size for c in kids), default=0)
        parent_size = dir_info.size or 1
        for child in kids:
            label = _tui_tree_label(child, max_size, parent_size)
            has_kids = bool(child.children)
            child_node = node.add(
                label, expand=False, allow_expand=has_kids
            )
            if has_kids:
                self._populate_tree_node(child_node, child)

    def action_rescan(self) -> None:
        self._start_scan()

    def action_toggle_hidden(self) -> None:
        self.show_hidden = not self.show_hidden
        state = "shown" if self.show_hidden else "hidden"
        self.query_one("#info-status", Label).update(
            Text(f"Hidden entries {state}", style=f"italic {_TUI_COLOR_WARN}")
        )
        if self.dir_info is not None:
            self._populate_ui()

    def action_expand_all(self) -> None:
        tree = self.query_one("#size-tree", Tree)
        tree.root.expand_all()

    def action_collapse_all(self) -> None:
        tree = self.query_one("#size-tree", Tree)
        tree.root.collapse_all()
        tree.root.expand()


# ─────────────────────────────────────────────────────────────────────── #
#                              CLI COMMANDS                               #
# ─────────────────────────────────────────────────────────────────────── #

def _resolve_report_format(
    output: Optional[Path], output_format: Optional[str]
) -> ReportFormat:
    """Resolve a ReportFormat from --format and/or --output; exits on error."""
    if output_format:
        try:
            return ReportFormat(output_format.lower())
        except ValueError:
            console.print(
                f"[bold red]Error: Unknown --format {output_format!r}. "
                f"Use: text, json, markdown, html[/bold red]"
            )
            raise typer.Exit(code=1)
    if output is not None:
        fmt = infer_report_format(output)
        if fmt is None:
            console.print(
                "[bold red]Error: Could not infer format from --output; "
                "use .txt, .json, .md, .html or pass --format[/bold red]"
            )
            raise typer.Exit(code=1)
        return fmt
    return ReportFormat.html


def _render_console_view(dir_info: DirInfo, target_path: Path, *, tree: bool, limit: int) -> None:
    """Render the classic terminal table/tree view for a scan result."""
    if tree:
        rich_tree = RichTree(f"[bold]{dir_info.name}[/bold] ({format_size(dir_info.size)})")
        build_rich_tree(rich_tree, dir_info, limit)
        console.print(rich_tree)
        return

    table = Table(title=f"Largest Items in {target_path}")
    table.add_column("#", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Size", justify="right", style="green")
    table.add_column("Files", justify="right")
    table.add_column("Dirs", justify="right")
    table.add_column("Type")

    for i, child in enumerate(dir_info.children[:limit], 1):
        item_type = "📁 Dir" if entry_is_directory(child) else "📄 File"
        table.add_row(
            str(i),
            child.name,
            format_size(child.size),
            str(child.file_count),
            str(child.dir_count),
            item_type,
        )

    console.print(table)


def _validate_scan_target(path: str) -> Path:
    """Resolve ``path`` and ensure it's an existing directory, or exit."""
    target_path = Path(path).resolve()

    if not target_path.exists():
        console.print(f"[bold red]Error: Path does not exist: {target_path}[/bold red]")
        raise typer.Exit(code=1)

    if not target_path.is_dir():
        console.print(f"[bold red]Error: Not a directory: {target_path}[/bold red]")
        raise typer.Exit(code=1)

    return target_path


def _scan_with_progress(target_path: Path, depth: Optional[int]) -> DirInfo:
    """Shared scan + progress + summary used by every scanning command."""
    console.print(f"[bold blue]Scanning: {target_path}[/bold blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Scanning...", total=None)
        cb = make_throttled_progress_cb(progress, task)
        dir_info = scan_directory(target_path, depth, progress_cb=cb)
        progress.update(
            task,
            description=(
                f"Scanned  "
                f"[bold green]{dir_info.file_count:,}[/bold green] files  "
                f"[bold green]{dir_info.dir_count:,}[/bold green] dirs  "
                f"[bold green]{format_size(dir_info.size)}[/bold green]"
            ),
        )

    console.print("\n[bold green]Scan complete[/bold green]")
    console.print(f"Total Size: [bold]{format_size(dir_info.size)}[/bold]")
    console.print(f"Files: {dir_info.file_count:,} | Directories: {dir_info.dir_count:,}\n")
    return dir_info


@app.command(
    short_help="Print the largest items to the terminal. Flags: -d DEPTH, -l LIMIT, -t (tree)."
)
def scan(
    path: str = typer.Argument(".", help="Directory to scan"),
    depth: Optional[int] = typer.Option(None, "-d", "--depth", help="Maximum depth to scan"),
    limit: int = typer.Option(20, "-l", "--limit", help="Number of items to show"),
    tree: bool = typer.Option(False, "-t", "--tree", help="Show as tree view"),
):
    """Scan a directory and print the largest items to the terminal.

    Use ``pytree report`` to generate an HTML/JSON/Markdown report file, or
    ``pytree tui`` for the interactive explorer.
    """
    target_path = _validate_scan_target(path)
    dir_info = _scan_with_progress(target_path, depth)
    _render_console_view(dir_info, target_path, tree=tree, limit=limit)


@app.command(
    short_help=(
        "Write an HTML/JSON/Markdown/text report file. "
        "Flags: -o FILE, --format FMT, --no-open, -d, -l, -t."
    )
)
def report(
    path: str = typer.Argument(".", help="Directory to scan"),
    depth: Optional[int] = typer.Option(None, "-d", "--depth", help="Maximum depth to scan"),
    limit: int = typer.Option(20, "-l", "--limit", help="Number of items to show"),
    tree: bool = typer.Option(False, "-t", "--tree", help="Render the report in tree form"),
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Write report to this file (default: a temp file)",
    ),
    output_format: Optional[str] = typer.Option(
        None,
        "--format",
        help="Report format: text, json, markdown, html (default: html)",
    ),
    no_open: bool = typer.Option(
        False,
        "--no-open",
        help="Do not launch the browser for HTML reports",
    ),
):
    """Generate a report file from a scan.

    Defaults to an interactive HTML report written to a temp file and opened
    in your default browser. Pass ``-o PATH`` to save it somewhere persistent,
    ``--format`` to pick text/json/markdown/html, or ``--no-open`` to skip the
    browser launch.
    """
    target_path = _validate_scan_target(path)
    dir_info = _scan_with_progress(target_path, depth)

    fmt = _resolve_report_format(output, output_format)
    report_path = output if output is not None else make_temp_report_path(target_path, fmt)
    write_scan_report(dir_info, target_path, report_path, fmt, tree_view=tree, limit=limit)

    is_temp = output is None
    label = "Generated" if is_temp else "Wrote"
    console.print(
        f"[bold green]{label} {fmt.value} report:[/bold green] [cyan]{report_path}[/cyan]"
    )

    should_open = fmt == ReportFormat.html and not no_open
    if should_open:
        if open_in_browser(report_path):
            console.print("[dim]Opened in your default browser.[/dim]")
        else:
            console.print(
                "[yellow]Could not launch a browser automatically; "
                "open the file above manually.[/yellow]"
            )


def build_rich_tree(parent, dir_info: DirInfo, limit: int, current_level: int = 0, max_level: int = 3):
    """Build Rich tree recursively."""
    if current_level >= max_level:
        return

    for child in dir_info.children[:limit]:
        label = f"{child.name} ({format_size(child.size)})"
        if child.children:
            branch = parent.add(f"[bold cyan]{label}[/bold cyan]")
            build_rich_tree(branch, child, limit, current_level + 1, max_level)
        else:
            parent.add(f"[dim]{label}[/dim]")


@app.command(
    short_help="Launch the interactive Textual explorer (arrow keys / enter to drill in). Flag: -d DEPTH."
)
def tui(
    path: str = typer.Argument(".", help="Directory to scan"),
    depth: Optional[int] = typer.Option(None, "-d", "--depth", help="Maximum depth to scan"),
):
    """Launch interactive TUI mode."""
    target_path = _validate_scan_target(path)
    app_instance = SizeTreeApp(target_path, depth)
    app_instance.run()


@app.command(short_help="Print version info (same as --version / -V).")
def version():
    """Show version information."""
    _print_version()


_INTERACTIVE_ACTIONS = ("scan", "report", "tui", "version")


def _prompt_interactive_args() -> List[str]:
    """Build a CLI argv list by interactively prompting the user.

    Used when pytree is launched with no arguments so first-time users see
    a friendly walkthrough instead of a silent default scan. The resulting
    argv is handed straight to Typer so option parsing stays single-source.
    """
    console.print(
        "[bold cyan]pytree[/bold cyan] — no command given. "
        "Answer a few prompts (Ctrl+C to cancel).\n"
    )

    action = Prompt.ask(
        "What do you want to do?",
        choices=list(_INTERACTIVE_ACTIONS),
        default="report",
    )
    if action == "version":
        return ["version"]

    path = Prompt.ask("Directory to scan", default=".")
    argv: List[str] = [action, path]

    depth_raw = Prompt.ask(
        "Maximum depth to scan (blank = unlimited)", default=""
    ).strip()
    if depth_raw:
        argv += ["-d", depth_raw]

    if action == "tui":
        return argv

    limit_raw = Prompt.ask("Number of items to show", default="20").strip()
    if limit_raw and limit_raw != "20":
        argv += ["-l", limit_raw]

    if Confirm.ask("Show as tree view?", default=False):
        argv.append("-t")

    if action == "scan":
        return argv

    output_raw = Prompt.ask(
        "Save report to file? (path, or blank for a temp HTML file)", default=""
    ).strip()
    if output_raw:
        argv += ["-o", output_raw]
        if infer_report_format(Path(output_raw)) is None:
            fmt = Prompt.ask(
                "Report format",
                choices=[f.value for f in ReportFormat],
                default=ReportFormat.html.value,
            )
            argv += ["--format", fmt]

    if not Confirm.ask("Open the HTML report in your browser?", default=True):
        argv.append("--no-open")

    return argv


if __name__ == "__main__":
    if len(sys.argv) == 1:
        try:
            sys.argv.extend(_prompt_interactive_args())
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Cancelled.[/dim]")
            sys.exit(130)
    # If first arg is not a command and not an option, treat it as a path for scan
    elif (
        len(sys.argv) >= 2
        and not sys.argv[1].startswith("-")
        and sys.argv[1] not in _INTERACTIVE_ACTIONS
    ):
        sys.argv = [sys.argv[0], "scan", sys.argv[1]] + sys.argv[2:]
    app()
