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
        '<button type="button" class="btn viz-tb-btn" id="viz-show-all" title="Include every item in the chart">Show all</button> '
        '<button type="button" class="btn viz-tb-btn" id="viz-hide-all" title="Hide every segment (chart empty)">Hide all</button> '
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


def _html_merge_groups_for_children(
    parent: DirInfo,
    esc,
    limit: int,
    max_depth: int,
    depth: int,
    *,
    share_base: int,
    color_offset: int,
    show_index: bool,
) -> str:
    """Recursive: tbody.merge-group blocks (data row + optional nested subtree table)."""
    if depth >= max_depth:
        return ""

    parts: List[str] = []
    base = max(share_base, 1)
    kids = parent.children[:limit]
    max_size = max((c.size for c in kids), default=0)
    max_files = max((c.file_count for c in kids), default=0)
    max_dirs = max((c.dir_count for c in kids), default=0)

    for i, child in enumerate(kids):
        item_type = "Dir" if entry_is_directory(child) else "File"
        kind = "dir" if item_type == "Dir" else "file"
        pct = 100.0 * child.size / base
        bar_color = _HTML_CHART_COLORS[(color_offset + i) % len(_HTML_CHART_COLORS)]
        is_dir = entry_is_directory(child)
        nested_allowed = is_dir and depth + 1 < max_depth
        inner_tbodies = ""
        if nested_allowed:
            inner_tbodies = _html_merge_groups_for_children(
                child,
                esc,
                limit,
                max_depth,
                depth + 1,
                share_base=max(child.size, 1),
                color_offset=color_offset + i + 1,
                show_index=False,
            )
        has_nested_block = nested_allowed and (
            inner_tbodies.strip() != "" or (is_dir and not child.children)
        )

        idx_cell = (
            f'<td class="num col-idx">{i + 1}</td>'
            if show_index
            else '<td class="num idx-muted">—</td>'
        )

        name_inner = f'<span class="entry-name">{esc(child.name)}</span>'
        if is_dir and has_nested_block:
            open_here = depth < 1
            aria_exp = "true" if open_here else "false"
            name_inner = (
                f'<button type="button" class="row-expand" aria-expanded="{aria_exp}" '
                'aria-label="Toggle folder contents"></button> ' + name_inner
            )
        elif is_dir and not child.children:
            name_inner = '<span class="dir-leaf"></span> ' + name_inner

        def _pill(value_html: str, bg: str) -> str:
            if not bg:
                return value_html
            return f'<span class="heat-pill" style="background:{bg}">{value_html}</span>'

        size_pill = _pill(esc(format_size(child.size)), _heat_bg(child.size, max_size))
        files_pill = _pill(f"{child.file_count:,}", _heat_bg(child.file_count, max_files))
        dirs_pill = _pill(f"{child.dir_count:,}", _heat_bg(child.dir_count, max_dirs))

        type_cell = (
            f'<td class="col-type">'
            f'<span class="badge" data-kind="{kind}">{esc(item_type)}</span>'
            "</td>"
        )

        main_row = (
            "<tr class=\"row-main\">"
            f"{idx_cell}"
            f'<td class="name name-depth-{depth}">{name_inner}</td>'
            '<td class="share-cell">'
            f'<div class="share-bar" title="{pct:.1f}%"><span style="width:{min(100.0, pct):.4f}%;background:{bar_color}"></span></div>'
            f'<span class="share-pct">{pct:.1f}%</span></td>'
            f'<td class="num size">{size_pill}</td>'
            f'<td class="num">{files_pill}</td>'
            f'<td class="num">{dirs_pill}</td>'
            f"{type_cell}"
            "</tr>"
        )

        nested_row = ""
        if is_dir and has_nested_block:
            open_here = depth < 1
            disp = "" if open_here else ' style="display:none"'
            if inner_tbodies.strip():
                nested_body = f'<table class="inner-tree">{inner_tbodies}</table>'
            else:
                nested_body = '<span class="nest-empty">Empty folder</span>'
            nested_row = (
                f'<tr class="row-nested"{disp}><td colspan="7" class="nested-cell">'
                f'<div class="nest-wrap depth-{depth}">{nested_body}</div></td></tr>'
            )

        viz_idx_attr = f' data-viz-idx="{i}"' if show_index else ""
        parts.append(
            '<tbody class="merge-group"'
            ' data-sort-name="' + esc(child.name) + '"'
            f' data-size="{child.size}" data-files="{child.file_count}"'
            f' data-dirs="{child.dir_count}" data-kind="{0 if kind == "dir" else 1}"'
            f' data-pct="{pct:.6f}"{viz_idx_attr}'
            f">{main_row}{nested_row}</tbody>"
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

    merged_tbodies = _html_merge_groups_for_children(
        dir_info,
        esc,
        limit,
        28,
        0,
        share_base=total_sz,
        color_offset=0,
        show_index=True,
    )
    table_body = (
        merged_tbodies
        if merged_tbodies.strip()
        else '<tbody><tr><td colspan="7" class="empty">No items</td></tr></tbody>'
    )

    root_line = (
        f'<div class="tree-root-label"><strong>{esc(dir_info.name)}</strong> '
        f'<span class="tree-meta">{esc(format_size(dir_info.size))}</span></div>'
    )
    table_section = (
        '<section class="panel" id="pytree-table-panel">'
        "<h2>Contents</h2>"
        '<p class="table-hint">'
        "Click column headers to sort <strong>top-level</strong> items (share = % of total scan). "
        "Each folder row can open nested contents; nested <strong>Share</strong> is % of that folder."
        "</p>"
        '<div class="tree-toolbar">'
        '<input type="search" id="tree-filter" class="tree-filter" '
        'placeholder="Filter top-level by name..." autocomplete="off" spellcheck="false" />'
        '<button type="button" class="btn" id="tree-expand-all">Expand all folders</button>'
        '<button type="button" class="btn" id="tree-collapse-all">Collapse all folders</button>'
        '<span class="tree-filter-status" id="tree-filter-status"></span>'
        "</div>"
        '<div class="table-wrap merged-tree-table">'
        f"{root_line}"
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
  max-width: 1440px;
  margin: 0 auto;
  padding: 2rem 1.5rem 3rem;
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
thead th:nth-child(7) { text-align: center; }
tbody td.col-type { text-align: center; font-size: 0.8rem; color: var(--muted); }
.heat-pill {
  display: inline-block;
  padding: 0.12rem 0.55rem;
  border-radius: 999px;
  min-width: 2.5rem;
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: #f6f8fa;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.55);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}
td.size .heat-pill { font-family: var(--mono); font-size: 0.82rem; }
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
.tree-filter {
  flex: 1 1 220px;
  min-width: 180px;
  max-width: 360px;
  font: inherit;
  font-size: 0.85rem;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  outline: none;
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}
.tree-filter::placeholder { color: var(--muted); }
.tree-filter:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-dim); }
.tree-filter-status { font-size: 0.8rem; color: var(--muted); margin-left: auto; }
tbody.merge-group.viz-highlight > tr.row-main > td {
  background: rgba(88, 166, 255, 0.14);
  box-shadow: inset 3px 0 0 var(--accent);
}
tbody.merge-group.row-hidden { display: none; }
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
.merged-tree-table {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.75rem;
  background: var(--bg-elevated);
  max-height: min(85vh, 1200px);
  overflow: auto;
}
.merged-tree-table table { border-collapse: collapse; }
.merged-tree-table .inner-tree {
  width: 100%;
  font-size: 0.88rem;
  border-collapse: collapse;
}
.merged-tree-table .inner-tree tbody.merge-group .row-main { background: rgba(13,17,23,0.5); }
.nested-cell {
  padding: 0.35rem 0.5rem 0.85rem 0.75rem !important;
  vertical-align: top !important;
  background: #0d1117;
  border-bottom: 1px solid #21262d;
}
.nest-wrap { border-left: 2px solid #30363d; margin: 0.15rem 0 0.35rem 0.35rem; padding: 0.35rem 0 0 0.65rem; }
.nest-wrap.depth-0 { margin-left: 0.25rem; }
.row-expand {
  display: inline-block;
  width: 1.2rem;
  height: 1.2rem;
  margin-right: 0.25rem;
  padding: 0;
  vertical-align: middle;
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
.dir-leaf { display: inline-block; width: 1.2rem; margin-right: 0.25rem; }
.idx-muted { color: var(--muted); text-align: center; }
.nest-empty { color: var(--muted); font-style: italic; font-size: 0.85rem; padding: 0.35rem; }
td.name.name-depth-1 { padding-left: 1rem; }
td.name.name-depth-2 { padding-left: 1.5rem; }
td.name.name-depth-3 { padding-left: 2rem; }
.tree-meta { color: var(--muted); font-weight: normal; }
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
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
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
    var headers = table.querySelectorAll("thead th[data-sort-key]");
    var current = { key: "size", dir: "desc" };

    function topLevelGroups() {
      return Array.prototype.slice.call(table.children).filter(function (el) {
        return el.tagName === "TBODY" && el.classList.contains("merge-group");
      });
    }

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

      var groups = topLevelGroups();
      groups.sort(function (a, b) {
        return cmp(a, b, current.key, current.dir);
      });
      var frag = document.createDocumentFragment();
      groups.forEach(function (tbody, i) {
        var idx = tbody.querySelector("tr.row-main .col-idx");
        if (idx) idx.textContent = String(i + 1);
        frag.appendChild(tbody);
      });
      var thead = table.querySelector("thead");
      if (thead) {
        table.insertBefore(frag, thead.nextSibling);
      }
    }

    headers.forEach(function (th) {
      th.addEventListener("click", function () {
        applySort(th.getAttribute("data-sort-key"), true);
      });
    });
    applySort("size", false);

    table.addEventListener("click", function (ev) {
      var btn = ev.target.closest(".row-expand");
      if (!btn || !table.contains(btn)) return;
      var tb = btn.closest("tbody.merge-group");
      if (!tb) return;
      var nest = tb.querySelector("tr.row-nested");
      if (!nest) return;
      var hidden = nest.style.display === "none";
      nest.style.display = hidden ? "" : "none";
      btn.setAttribute("aria-expanded", hidden ? "true" : "false");
    });
  }

  var expandBtn = document.getElementById("tree-expand-all");
  var collapseBtn = document.getElementById("tree-collapse-all");
  var panel = document.getElementById("pytree-table-panel");
  if (panel && expandBtn && collapseBtn) {
    expandBtn.addEventListener("click", function () {
      panel.querySelectorAll("tr.row-nested").forEach(function (tr) {
        tr.style.display = "";
      });
      panel.querySelectorAll(".row-expand").forEach(function (b) {
        b.setAttribute("aria-expanded", "true");
      });
    });
    collapseBtn.addEventListener("click", function () {
      panel.querySelectorAll("tr.row-nested").forEach(function (tr) {
        tr.style.display = "none";
      });
      panel.querySelectorAll(".row-expand").forEach(function (b) {
        b.setAttribute("aria-expanded", "false");
      });
    });
  }

  var filterInput = document.getElementById("tree-filter");
  var filterStatus = document.getElementById("tree-filter-status");
  var mainTable = document.getElementById("pytree-items");
  if (filterInput && mainTable) {
    var topGroups = Array.prototype.slice.call(
      mainTable.querySelectorAll(":scope > tbody.merge-group")
    );
    function applyFilter() {
      var q = (filterInput.value || "").trim().toLowerCase();
      var shown = 0;
      topGroups.forEach(function (g) {
        var name = (g.getAttribute("data-sort-name") || "").toLowerCase();
        var match = !q || name.indexOf(q) !== -1;
        g.classList.toggle("row-hidden", !match);
        if (match) shown += 1;
      });
      if (filterStatus) {
        if (!q) {
          filterStatus.textContent = "";
        } else {
          filterStatus.textContent =
            shown + " of " + topGroups.length + " match";
        }
      }
    }
    filterInput.addEventListener("input", applyFilter);
    filterInput.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        filterInput.value = "";
        applyFilter();
      }
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
      '#pytree-items > tbody.merge-group[data-viz-idx="' + idx + '"]'
    );
    rows.forEach(function (r) { r.classList.add("viz-highlight"); });
  }
  function clearRowHighlight() {
    document
      .querySelectorAll("#pytree-items > tbody.merge-group.viz-highlight")
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
