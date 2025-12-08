#!/usr/bin/env python3
"""
SizeTree - A TreeSize-like disk space analyzer
Built with Textual for interactive TUI and CLI support
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Tuple
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

app = typer.Typer(rich_markup_mode="rich")
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
                    total_size += item.stat().st_size
                    file_count += 1
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
):
    """Scan directory and show size information (CLI mode)."""
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
    
    console.print(f"\n[bold green]✓ Scan complete[/bold green]")
    console.print(f"Total Size: [bold]{format_size(dir_info.size)}[/bold]")
    console.print(f"Files: {dir_info.file_count:,} | Directories: {dir_info.dir_count:,}\n")
    
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
            item_type = "📁 Dir" if child.dir_count > 0 or child.children else "📄 File"
            table.add_row(
                str(i),
                child.name,
                format_size(child.size),
                str(child.file_count),
                str(child.dir_count),
                item_type
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
