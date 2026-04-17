#!/usr/bin/env python3
"""
SizeTree - A TreeSize-like disk space analyzer
Built with Textual for interactive TUI and CLI support
"""

import html
import json
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
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


def render_report_html(
    dir_info: DirInfo,
    target_path: Path,
    *,
    tree_view: bool,
    limit: int,
) -> str:
    """HTML5 report with dark theme (default)."""
    esc = html.escape
    path_s = str(target_path)
    title_plain = f"Disk usage - {path_s}"
    title_esc = esc(title_plain)
    gen = esc(datetime.now().isoformat(timespec="seconds"))
    size_h = esc(format_size(dir_info.size))

    if tree_view:
        tree_lines = build_plain_tree_lines(dir_info, limit)
        pre = esc("\n".join(tree_lines))
        body = (
            '<section class="panel">\n'
            '<h2>Directory tree</h2>\n'
            f'<pre class="tree" role="region" aria-label="Directory tree">{pre}</pre>\n'
            "</section>\n"
        )
    else:
        rows: List[str] = []
        for i, child in enumerate(dir_info.children[:limit], 1):
            item_type = "Dir" if entry_is_directory(child) else "File"
            kind = "dir" if item_type == "Dir" else "file"
            rows.append(
                "<tr>"
                f'<td class="num">{i}</td>'
                f'<td class="name"><span class="badge" data-kind="{kind}">{esc(item_type)}</span>'
                f"{esc(child.name)}</td>"
                f'<td class="num size">{esc(format_size(child.size))}</td>'
                f'<td class="num">{child.file_count:,}</td>'
                f'<td class="num">{child.dir_count:,}</td>'
                "</tr>"
            )
        tbody = "\n".join(rows) if rows else '<tr><td colspan="5" class="empty">No items</td></tr>'
        body = (
            '<section class="panel">\n'
            "<h2>Largest items</h2>\n"
            '<div class="table-wrap">\n'
            '<table>\n'
            "<thead><tr>"
            "<th>#</th><th>Name</th><th>Size</th><th>Files</th><th>Dirs</th>"
            "</tr></thead>\n"
            f"<tbody>\n{tbody}\n</tbody>\n"
            "</table>\n</div>\n</section>\n"
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
thead th:nth-child(n+3) { text-align: right; }
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
        "</div>\n</body>\n</html>\n"
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
