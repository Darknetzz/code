#!/usr/bin/env python3
"""
SizeTree - A TreeSize-like disk space analyzer
Built with Textual for interactive TUI and CLI support
"""

import html
import json
import math
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree as RichTree
from rich.progress import Progress, SpinnerColumn, TextColumn

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Tree, Static, Button, Input, Label
from textual.reactive import reactive
from textual.binding import Binding

app = typer.Typer(
    rich_markup_mode="rich",
    help=(
        "Disk space analyzer (CLI + TUI). "
        "Most CLI flags, including saving reports (-o / --output, --format), "
        "are on the scan command. Run: pytree scan --help"
    ),
)
console = Console()

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

def scan_directory(path: Path, max_depth: Optional[int] = None, current_depth: int = 0) -> DirInfo:
    """Recursively scan directory and calculate sizes."""
    total_size = 0
    file_count = 0
    dir_count = 0
    children = []
    error = None

    try:
        items = list(path.iterdir())
        
        for item in items:
            try:
                if item.is_file():
                    sz = item.stat().st_size
                    total_size += sz
                    file_count += 1
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
                    
                    # Recursively scan subdirectories if within depth limit
                    if max_depth is None or current_depth < max_depth:
                        child_info = scan_directory(item, max_depth, current_depth + 1)
                        children.append(child_info)
                        total_size += child_info.size
                        file_count += child_info.file_count
                        dir_count += child_info.dir_count
                    else:
                        # Just get size without recursing
                        child_size = get_dir_size(item)
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
                # Skip items we can't access
                continue
            except Exception as e:
                # Log other errors but continue
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


def get_dir_size(path: Path) -> int:
    """Get total size of directory without detailed recursion."""
    total = 0
    try:
        for item in path.rglob('*'):
            try:
                if item.is_file():
                    total += item.stat().st_size
            except:
                continue
    except:
        pass
    return total


def format_size(size: int) -> str:
    """Format size in human-readable format."""
    size_float = float(size)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_float < 1024.0:
            return f"{size_float:.1f} {unit}"
        size_float /= 1024.0
    return f"{size_float:.1f} PB"


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
    segments: List[Tuple[int, str]],
    total: int,
    *,
    cx: float = 100.0,
    cy: float = 100.0,
    outer_r: float = 78.0,
    inner_r: float = 44.0,
) -> str:
    """segments: (size_bytes, color_hex). Returns SVG path elements."""
    if total <= 0 or not segments:
        return ""
    start = -math.pi / 2
    paths: List[str] = []
    for size, color in segments:
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
            f'<path d="M {x0o:.2f} {y0o:.2f} A {outer_r} {outer_r} 0 {large} 1 {x1o:.2f} {y1o:.2f} '
            f"L {x1i:.2f} {y1i:.2f} A {inner_r} {inner_r} 0 {large} 0 {x0i:.2f} {y0i:.2f} Z\" "
            f'fill="{color}" stroke="#0d1117" stroke-width="1"/>'
        )
        start = a1
    return "".join(paths)


def _html_storage_viz_block(dir_info: DirInfo, esc, limit: int) -> str:
    """Donut SVG + stacked bar + legend for direct children."""
    kids = list(dir_info.children[: max(limit, 24)])
    total = dir_info.size or 1
    if not kids:
        return '<p class="viz-empty">No direct items to chart.</p>'

    chart_items: List[Tuple[str, int, str]] = []
    for i, ch in enumerate(kids):
        chart_items.append((ch.name, ch.size, _HTML_CHART_COLORS[i % len(_HTML_CHART_COLORS)]))

    seg_data = [(sz, col) for _nm, sz, col in chart_items]
    paths = _svg_donut_slices(seg_data, total)

    legend_rows = []
    for name, size, color in chart_items:
        pct = 100.0 * size / total
        legend_rows.append(
            "<div class=\"legend-row\">"
            f"<span class=\"swatch\" style=\"background:{color}\"></span>"
            f"<span class=\"legend-name\">{esc(name)}</span>"
            f"<span class=\"legend-pct\">{pct:.1f}%</span>"
            f"<span class=\"legend-sz\">{esc(format_size(size))}</span>"
            "</div>"
        )

    stacked_parts = []
    for name, size, color in chart_items:
        w = max(0.0, 100.0 * size / total)
        stacked_parts.append(
            f"<span style=\"width:{w:.3f}%;background:{color}\" "
            f"title=\"{esc(name)} — {esc(format_size(size))}\"></span>"
        )

    donut = (
        f'<div class="donut-wrap"><svg viewBox="0 0 200 200" class="donut-svg" '
        'role="img" aria-label="Storage share by item">'
        f"<defs><filter id=\"glow\"><feGaussianBlur stdDeviation=\"0.5\" result=\"b\"/>"
        f"<feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter></defs>"
        f"{paths}</svg></div>"
    )
    legend = '<div class="legend-col">' + "\n".join(legend_rows) + "</div>"
    stacked = (
        '<div class="stacked-hbar" role="img" aria-label="Relative size of each item">'
        + "".join(stacked_parts)
        + "</div>"
    )
    return (
        '<div class="storage-viz">'
        f"{donut}"
        f'<div class="viz-side"><h3 class="viz-title">Share of scanned folder</h3>{stacked}'
        f"{legend}</div></div>"
    )


def _html_expandable_tree(
    node: DirInfo,
    esc,
    limit: int,
    max_depth: int,
    depth: int = 0,
) -> str:
    """Nested <details> for directories, div rows for files."""
    if depth >= max_depth:
        return '<div class="tree-limit">…</div>'

    parts: List[str] = []
    for child in node.children[:limit]:
        if entry_is_directory(child):
            label = f"{esc(child.name)} <span class=\"tree-meta\">{esc(format_size(child.size))}</span>"
            open_attr = " open" if depth < 1 else ""
            if child.children:
                inner = _html_expandable_tree(child, esc, limit, max_depth, depth + 1)
                parts.append(
                    f'<details class="tree-node"{open_attr}><summary>{label}</summary>'
                    f'<div class="tree-children">{inner}</div></details>'
                )
            else:
                parts.append(
                    f'<details class="tree-node tree-node-empty"{open_attr}><summary>{label}</summary>'
                    "<div class=\"tree-children\"><span class=\"tree-empty\">Empty</span></div></details>"
                )
        else:
            parts.append(
                '<div class="tree-leaf">'
                f"{esc(child.name)} <span class=\"tree-meta\">{esc(format_size(child.size))}</span>"
                "</div>"
            )
    return "\n".join(parts)


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

    rows: List[str] = []
    for i, child in enumerate(dir_info.children[:limit], 1):
        item_type = "Dir" if entry_is_directory(child) else "File"
        kind = "dir" if item_type == "Dir" else "file"
        pct = 100.0 * child.size / total_sz
        bar_color = _HTML_CHART_COLORS[(i - 1) % len(_HTML_CHART_COLORS)]
        rows.append(
            "<tr"
            ' data-sort-name="' + esc(child.name) + '"'
            f' data-size="{child.size}" data-files="{child.file_count}"'
            f' data-dirs="{child.dir_count}" data-kind="{0 if kind == "dir" else 1}"'
            f' data-pct="{pct:.6f}"'
            ">"
            f'<td class="num col-idx">{i}</td>'
            f'<td class="name"><span class="badge" data-kind="{kind}">{esc(item_type)}</span>'
            f"{esc(child.name)}</td>"
            '<td class="share-cell">'
            f'<div class="share-bar" title="{pct:.1f}%"><span style="width:{min(100.0, pct):.4f}%;background:{bar_color}"></span></div>'
            f'<span class="share-pct">{pct:.1f}%</span></td>'
            f'<td class="num size col-size">{esc(format_size(child.size))}</td>'
            f'<td class="num col-files">{child.file_count:,}</td>'
            f'<td class="num col-dirs">{child.dir_count:,}</td>'
            f'<td class="col-type">{esc(item_type)}</td>'
            "</tr>"
        )
    tbody = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="7" class="empty">No items</td></tr>'
    )

    tree_inner = _html_expandable_tree(dir_info, esc, limit, 28)
    root_label = (
        f'<div class="tree-root-label"><strong>{esc(dir_info.name)}</strong> '
        f'<span class="tree-meta">{esc(format_size(dir_info.size))}</span></div>'
    )
    tree_section = (
        '<section class="panel panel-tree" id="pytree-tree">'
        "<h2>Directory structure</h2>"
        '<p class="tree-hint">Click folder rows to expand or collapse. Use the buttons below for all folders at once.</p>'
        '<div class="tree-toolbar">'
        '<button type="button" class="btn" id="tree-expand-all">Expand all</button> '
        '<button type="button" class="btn" id="tree-collapse-all">Collapse all</button>'
        "</div>"
        f'<div class="interactive-tree">{root_label}{tree_inner}</div>'
        "</section>"
    )

    table_section = (
        '<section class="panel">'
        "<h2>Largest items (this folder)</h2>"
        '<p class="table-hint">Click a column header to sort. Share is percent of total scanned size.</p>'
        '<div class="table-wrap">'
        '<table id="pytree-items">'
        "<thead><tr>"
        '<th class="num">#</th>'
        '<th class="sortable" data-sort-key="name" scope="col">Name</th>'
        '<th class="sortable" data-sort-key="pct" scope="col">Share</th>'
        '<th class="sortable sort-desc" data-sort-key="size" scope="col">Size</th>'
        '<th class="sortable" data-sort-key="files" scope="col">Files</th>'
        '<th class="sortable" data-sort-key="dirs" scope="col">Dirs</th>'
        '<th class="sortable" data-sort-key="kind" scope="col">Type</th>'
        "</tr></thead>"
        f"<tbody>{tbody}</tbody>"
        "</table></div></section>"
    )

    body = (
        '<section class="panel panel-viz"><h2>Storage overview</h2>'
        f"{viz_html}</section>\n{table_section}\n{tree_section}"
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
  max-width: 1040px;
  margin: 0 auto;
  padding: 2rem 1.25rem 3rem;
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
thead th:nth-child(7) { text-align: center; }
tbody td.col-type { text-align: center; font-size: 0.8rem; color: var(--muted); }
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
.panel-viz h2, .panel-tree h2 { margin-top: 0; }
.table-hint, .tree-hint {
  margin: 0 0 1rem;
  font-size: 0.82rem;
  color: var(--muted);
}
.storage-viz {
  display: grid;
  grid-template-columns: minmax(160px, 220px) 1fr;
  gap: 1.25rem 1.5rem;
  align-items: start;
}
@media (max-width: 720px) {
  .storage-viz { grid-template-columns: 1fr; }
}
.donut-wrap { justify-self: center; }
.donut-svg { width: 100%; max-width: 220px; height: auto; display: block; filter: drop-shadow(0 4px 12px rgba(0,0,0,.4)); }
.viz-side { min-width: 0; }
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
  height: 14px;
  border-radius: 7px;
  overflow: hidden;
  background: #21262d;
  margin-bottom: 1rem;
  box-shadow: inset 0 1px 3px rgba(0,0,0,.35);
}
.stacked-hbar > span {
  display: block;
  height: 100%;
  min-width: 0;
  transition: opacity 0.15s ease;
}
.stacked-hbar > span:hover { opacity: 0.92; }
.legend-col { display: flex; flex-direction: column; gap: 0.35rem; max-height: 280px; overflow-y: auto; }
.legend-row {
  display: grid;
  grid-template-columns: 12px 1fr auto auto;
  gap: 0.5rem 0.75rem;
  align-items: center;
  font-size: 0.82rem;
}
.legend-row .swatch {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  border: 1px solid rgba(255,255,255,.12);
}
.legend-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
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
.tree-toolbar { margin-bottom: 0.75rem; }
.btn {
  font: inherit;
  font-size: 0.85rem;
  padding: 0.35rem 0.85rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: #21262d;
  color: var(--text);
  cursor: pointer;
}
.btn:hover { background: #30363d; border-color: var(--accent); }
.interactive-tree {
  font-family: var(--mono);
  font-size: 0.84rem;
  line-height: 1.5;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem 0.5rem 0.75rem 0.75rem;
  background: var(--bg);
  max-height: min(70vh, 900px);
  overflow: auto;
}
.interactive-tree details { margin: 0.15rem 0 0.15rem 0.25rem; }
.interactive-tree summary {
  cursor: pointer;
  list-style: none;
  padding: 0.2rem 0.35rem;
  border-radius: 4px;
}
.interactive-tree summary::-webkit-details-marker { display: none; }
.interactive-tree summary::before {
  content: "\\25B6";
  display: inline-block;
  margin-right: 0.35rem;
  font-size: 0.65em;
  opacity: 0.7;
  transition: transform 0.15s ease;
}
.interactive-tree details[open] > summary::before { transform: rotate(90deg); }
.interactive-tree summary:hover { background: #21262d; }
.tree-children { margin: 0.25rem 0 0.35rem 0.85rem; padding-left: 0.5rem; border-left: 1px solid #30363d; }
.tree-meta { color: var(--muted); font-weight: normal; }
.tree-leaf { padding: 0.15rem 0.35rem 0.15rem 1.2rem; color: #8b949e; }
.tree-limit, .tree-empty { color: var(--muted); font-style: italic; padding: 0.2rem; }
tbody tr {
  border-bottom: 1px solid #21262d;
  transition: background 0.12s ease;
}
tbody tr:hover { background: #1f242c; }
tbody td {
  padding: 0.6rem 0.75rem;
  vertical-align: middle;
}
tbody td.num { text-align: right; font-variant-numeric: tabular-nums; }
tbody td.name { word-break: break-word; }
tbody td.empty {
  text-align: center;
  color: var(--muted);
  padding: 1.5rem;
}
.badge {
  display: inline-block;
  margin-right: 0.5rem;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  vertical-align: middle;
}
.badge[data-kind="dir"] { color: var(--dir); background: #2d1f3d; border: 1px solid #4c2889; }
.badge[data-kind="file"] { color: var(--file); background: #102a4c; border: 1px solid #1f6feb; }
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
        f"<dt>Contents</dt><dd>{dir_info.file_count:,} files &middot; "
        f"{dir_info.dir_count:,} directories</dd>\n"
        "</dl>\n</header>\n"
    )

    script = """
<script>
(function () {
  var table = document.getElementById("pytree-items");
  if (table) {
    var tbody = table.querySelector("tbody");
    var headers = table.querySelectorAll("thead th[data-sort-key]");
    var current = { key: "size", dir: "desc" };

    function clearSortMarks() {
      headers.forEach(function (th) {
        th.classList.remove("sort-asc", "sort-desc");
      });
    }

    function cmp(a, b, key, dir) {
      var mul = dir === "asc" ? 1 : -1;
      if (key === "name") {
        var ca = a.getAttribute("data-sort-name") || "";
        var cb = b.getAttribute("data-sort-name") || "";
        if (ca !== cb) {
          return mul * ca.localeCompare(cb, undefined, { numeric: true, sensitivity: "base" });
        }
      } else if (key === "kind") {
        var ka = parseInt(a.getAttribute("data-kind") || "0", 10);
        var kb = parseInt(b.getAttribute("data-kind") || "0", 10);
        if (ka !== kb) return mul * (ka - kb);
      } else {
        var ak = key === "pct" ? "data-pct" : "data-" + key;
        var va = parseFloat(a.getAttribute(ak) || "0");
        var vb = parseFloat(b.getAttribute(ak) || "0");
        if (va !== vb) return mul * (va - vb);
      }
      var ca = a.getAttribute("data-sort-name") || "";
      var cb = b.getAttribute("data-sort-name") || "";
      return ca.localeCompare(cb, undefined, { numeric: true, sensitivity: "base" });
    }

    function applySort(key, toggle) {
      if (toggle) {
        if (current.key === key) {
          current.dir = current.dir === "asc" ? "desc" : "asc";
        } else {
          current.key = key;
          current.dir = key === "name" || key === "kind" ? "asc" : "desc";
        }
      }
      clearSortMarks();
      var th = table.querySelector('thead th[data-sort-key="' + current.key + '"]');
      if (th) th.classList.add(current.dir === "asc" ? "sort-asc" : "sort-desc");

      var rows = Array.prototype.slice.call(tbody.querySelectorAll("tr[data-sort-name]"));
      rows.sort(function (a, b) {
        return cmp(a, b, current.key, current.dir);
      });
      rows.forEach(function (tr, i) {
        var idx = tr.querySelector(".col-idx");
        if (idx) idx.textContent = String(i + 1);
        tbody.appendChild(tr);
      });
    }

    headers.forEach(function (th) {
      th.addEventListener("click", function () {
        applySort(th.getAttribute("data-sort-key"), true);
      });
    });
    applySort("size", false);
  }

  var expandBtn = document.getElementById("tree-expand-all");
  var collapseBtn = document.getElementById("tree-collapse-all");
  var treeRoot = document.getElementById("pytree-tree");
  if (treeRoot && expandBtn && collapseBtn) {
    expandBtn.addEventListener("click", function () {
      treeRoot.querySelectorAll("details").forEach(function (d) {
        d.open = true;
      });
    });
    collapseBtn.addEventListener("click", function () {
      treeRoot.querySelectorAll("details").forEach(function (d) {
        d.open = false;
      });
    });
  }
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
        f"{script}"
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


# ─────────────────────────────────────────────────────────────────────── #
#                              TEXTUAL TUI APP                            #
# ─────────────────────────────────────────────────────────────────────── #

class SizeTreeApp(App):
    """Textual TUI for TreeSize-like functionality."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #info-panel {
        dock: top;
        height: 5;
        background: $primary-background;
        border: solid $primary;
    }
    
    #tree-container {
        height: 1fr;
        border: solid $secondary;
    }
    
    .info-label {
        padding: 1;
        color: $text;
    }
    
    Tree {
        scrollbar-gutter: stable;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "rescan", "Rescan"),
        Binding("h", "toggle_hidden", "Toggle Hidden"),
    ]
    
    def __init__(self, root_path: Path, max_depth: Optional[int] = None):
        super().__init__()
        self.root_path = root_path
        self.max_depth = max_depth
        self.dir_info: Optional[DirInfo] = None
        self.show_hidden = False

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        
        with Vertical(id="info-panel"):
            yield Label(f"Scanning: {self.root_path}", id="path-label", classes="info-label")
            yield Label("Total Size: Computing...", id="size-label", classes="info-label")
            yield Label("Files: 0 | Directories: 0", id="count-label", classes="info-label")
        
        with Container(id="tree-container"):
            yield Tree(str(self.root_path), id="size-tree")
        
        yield Footer()

    async def on_mount(self) -> None:
        """Scan directory on mount."""
        self.scan_and_populate()

    def scan_and_populate(self) -> None:
        """Scan directory and populate tree."""
        # Show scanning status
        self.query_one("#size-label", Label).update("Total Size: Scanning...")
        
        # Scan directory
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Scanning directories...", total=None)
            self.dir_info = scan_directory(self.root_path, self.max_depth)
            progress.update(task, completed=True)
        
        # Update info panel
        self.query_one("#size-label", Label).update(
            f"Total Size: {format_size(self.dir_info.size)}"
        )
        self.query_one("#count-label", Label).update(
            f"Files: {self.dir_info.file_count:,} | Directories: {self.dir_info.dir_count:,}"
        )
        
        # Populate tree
        tree = self.query_one("#size-tree", Tree)
        tree.clear()
        tree.root.label = f"{self.dir_info.name} ({format_size(self.dir_info.size)})"
        self.populate_tree_node(tree.root, self.dir_info)
        tree.root.expand()

    def populate_tree_node(self, node, dir_info: DirInfo) -> None:
        """Recursively populate tree nodes."""
        for child in dir_info.children[:20]:  # Limit to top 20 to avoid lag
            # Skip hidden files if needed
            if not self.show_hidden and child.name.startswith('.'):
                continue
            
            label = f"{child.name} ({format_size(child.size)})"
            if child.error:
                label += f" [Error: {child.error}]"
            
            child_node = node.add(label, expand=False)
            
            if child.children:
                self.populate_tree_node(child_node, child)

    def action_rescan(self) -> None:
        """Rescan the directory."""
        self.scan_and_populate()

    def action_toggle_hidden(self) -> None:
        """Toggle showing hidden files."""
        self.show_hidden = not self.show_hidden
        if self.dir_info:
            tree = self.query_one("#size-tree", Tree)
            tree.clear()
            tree.root.label = f"{self.dir_info.name} ({format_size(self.dir_info.size)})"
            self.populate_tree_node(tree.root, self.dir_info)
            tree.root.expand()


# ─────────────────────────────────────────────────────────────────────── #
#                              CLI COMMANDS                               #
# ─────────────────────────────────────────────────────────────────────── #

@app.command()
def scan(
    path: str = typer.Argument(".", help="Directory to scan"),
    depth: Optional[int] = typer.Option(None, "-d", "--depth", help="Maximum depth to scan"),
    limit: int = typer.Option(20, "-l", "--limit", help="Number of items to show"),
    tree: bool = typer.Option(False, "-t", "--tree", help="Show as tree view"),
    output: Optional[Path] = typer.Option(
        None,
        "-o",
        "--output",
        help="Write report to this file (format from extension or --format)",
    ),
    output_format: Optional[str] = typer.Option(
        None,
        "--format",
        help="Report format: text, json, markdown, html (default: infer from --output)",
    ),
):
    """Scan a directory and print a size table or tree (CLI).

    Use -o / --output PATH to write a report; --format text|json|markdown|html,
    or infer format from the extension (.txt, .json, .md, .html).
    """
    target_path = Path(path).resolve()
    
    if not target_path.exists():
        console.print(f"[bold red]Error: Path does not exist: {target_path}[/bold red]")
        raise typer.Exit(code=1)
    
    if not target_path.is_dir():
        console.print(f"[bold red]Error: Not a directory: {target_path}[/bold red]")
        raise typer.Exit(code=1)
    
    console.print(f"[bold blue]Scanning: {target_path}[/bold blue]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning directories...", total=None)
        dir_info = scan_directory(target_path, depth)
        progress.remove_task(task)
    
    console.print("\n[bold green]Scan complete[/bold green]")
    console.print(f"Total Size: [bold]{format_size(dir_info.size)}[/bold]")
    console.print(f"Files: {dir_info.file_count:,} | Directories: {dir_info.dir_count:,}\n")

    fmt: Optional[ReportFormat] = None
    if output is not None:
        if output_format:
            try:
                fmt = ReportFormat(output_format.lower())
            except ValueError:
                console.print(
                    f"[bold red]Error: Unknown --format {output_format!r}. "
                    f"Use: text, json, markdown, html[/bold red]"
                )
                raise typer.Exit(code=1)
        else:
            fmt = infer_report_format(output)
            if fmt is None:
                console.print(
                    "[bold red]Error: Could not infer format from --output; "
                    "use .txt, .json, .md, .html or pass --format[/bold red]"
                )
                raise typer.Exit(code=1)
        write_scan_report(dir_info, target_path, output, fmt, tree_view=tree, limit=limit)
        console.print(f"[bold green]Wrote {fmt.value} report to[/bold green] [cyan]{output}[/cyan]")

    if output is None:
        if tree:
            # Show as tree view
            rich_tree = RichTree(f"[bold]{dir_info.name}[/bold] ({format_size(dir_info.size)})")
            build_rich_tree(rich_tree, dir_info, limit)
            console.print(rich_tree)
        else:
            # Show as table
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


@app.command()
def tui(
    path: str = typer.Argument(".", help="Directory to scan"),
    depth: Optional[int] = typer.Option(None, "-d", "--depth", help="Maximum depth to scan"),
):
    """Launch interactive TUI mode."""
    target_path = Path(path).resolve()
    
    if not target_path.exists():
        console.print(f"[bold red]Error: Path does not exist: {target_path}[/bold red]")
        raise typer.Exit(code=1)
    
    if not target_path.is_dir():
        console.print(f"[bold red]Error: Not a directory: {target_path}[/bold red]")
        raise typer.Exit(code=1)
    
    app_instance = SizeTreeApp(target_path, depth)
    app_instance.run()


@app.command()
def version():
    """Show version information."""
    console.print("[bold]SizeTree[/bold] v1.0.0")
    console.print("A TreeSize-like disk space analyzer built with Textual")


if __name__ == "__main__":
    # Show help if no arguments provided
    if len(sys.argv) == 1:
        sys.argv.extend(["scan", "."])
    # If first arg is not a command and not an option, treat it as a path for scan
    elif len(sys.argv) >= 2 and not sys.argv[1].startswith('-') and sys.argv[1] not in ['scan', 'tui', 'version']:
        path = sys.argv[1]
        # Insert 'scan' command and keep the rest of the args
        sys.argv = [sys.argv[0], 'scan', path] + sys.argv[2:]
    app()
