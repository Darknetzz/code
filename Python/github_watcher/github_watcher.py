#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────── #
#                           GitHub Watcher v2.0                           #
#                         Rewritten with Typer                            #
# ─────────────────────────────────────────────────────────────────────── #

import requests
import json
import os
import time
from typing import Optional
from pathlib import Path

from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
import typer

app = typer.Typer(rich_markup_mode="rich")
console = Console()

# ─────────────────────────────────────────────────────────────────────── #
#                              CONSTANTS                                  #
# ─────────────────────────────────────────────────────────────────────── #
SCRIPT_VERSION = "2.0.0"
REPOS_FILE = "repos.json"
VERSION_FILE = "github_watcher.json"
CWD = os.path.dirname(os.path.abspath(__file__))

# Change to script directory
os.chdir(CWD)


# ─────────────────────────────────────────────────────────────────────── #
#                              UTILITIES                                  #
# ─────────────────────────────────────────────────────────────────────── #
def fetch(url: str) -> Optional[requests.Response]:
    """Fetch URL and return response."""
    try:
        return requests.get(url)
    except Exception as e:
        console.print(f"[bold red]Failed to fetch {url}: {e}[/bold red]")
        return None


def find(req: Optional[requests.Response], tagname: str, attributes: Optional[dict] = None) -> Optional[str]:
    """Find tag in HTML response."""
    if not req or not req.content:
        return None
    
    try:
        soup = BeautifulSoup(req.content, "html.parser")
        res = soup.find(name=tagname, attrs=attributes or {})
        
        if not res:
            return None
        
        return res.get_text(strip=True)
    except Exception as e:
        console.print(f"[yellow]find() error:[/yellow] {e}")
        return None


def load_repos(create_if_missing: bool = True) -> dict:
    """Load repos from JSON file. Create if missing and user confirms."""
    if not os.path.isfile(REPOS_FILE):
        if not create_if_missing:
            console.print(f"[bold red]Error: {REPOS_FILE} not found![/bold red]")
            raise typer.Exit(code=1)
        
        console.print(f"[bold yellow]{REPOS_FILE} not found.[/bold yellow]")
        create = typer.confirm("Create a new repos.json file?", default=True)
        
        if create:
            empty_repos = {}
            save_repos(empty_repos)
            console.print(f"[bold green]✅ Created {REPOS_FILE}[/bold green]")
            return empty_repos
        else:
            console.print("[bold red]Cannot proceed without repos.json[/bold red]")
            raise typer.Exit(code=1)
    
    with open(REPOS_FILE, 'r') as f:
        return json.load(f)


def save_repos(repos: dict) -> None:
    """Save repos to JSON file."""
    with open(REPOS_FILE, 'w') as f:
        json.dump(repos, f, indent=4)


def load_versions() -> dict:
    """Load cached versions from JSON file."""
    if os.path.isfile(VERSION_FILE):
        with open(VERSION_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_versions(versions: dict) -> None:
    """Save versions to JSON file."""
    with open(VERSION_FILE, 'w') as f:
        json.dump(versions, f, indent=4)


# ─────────────────────────────────────────────────────────────────────── #
#                              COMMANDS                                   #
# ─────────────────────────────────────────────────────────────────────── #

@app.command()
def check(
    wait: int = typer.Option(1, "-w", "--wait", help="Seconds between requests"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """Check all repos for new releases."""
    repos = load_repos()
    versions = load_versions()
    
    console.print(f"[bold blue]Checking {len(repos)} repo(s)...[/bold blue]")
    
    start = time.time()
    changes_count = 0
    new_versions = {}
    rows = []
    
    headers = ['#', 'Repo', 'Current Release', 'Date', 'Current Tag', 'Date']
    table = Table(title="GitHub Repo Overview")
    
    for header in headers:
        table.add_column(header)
    
    with console.status("[bold]Fetching repos...[/bold]") as status:
        for i, (repo_name, repo_url) in enumerate(repos.items()):
            counter = f"({i}/{len(repos)})"
            changes = False
            
            # Clean URL
            if repo_url.endswith('/'):
                repo_url = repo_url[:-1]
            
            author = repo_url.split('/')[-2]
            repo = repo_url.split('/')[-1]
            
            latest_url = f"{repo_url}/releases/latest"
            tags_url = f"{repo_url}/tags"
            
            # Fetch release and tags
            req_rel = fetch(latest_url)
            req_tag = fetch(tags_url)
            
            if not req_rel and not req_tag:
                console.print(f"[bold red]{counter} Failed to fetch {repo_name}[/bold red]")
                continue
            
            # Find tags
            tag_rel = find(req_rel, "h1", {"class": "d-inline mr-3"}) if req_rel else None
            tag_tag = find(req_tag, "a", {"class": "Link--primary Link"}) if req_tag else None
            
            if not tag_rel and not tag_tag:
                console.print(f"[yellow]{counter} No releases/tags for {repo_name}[/yellow]")
                tag_rel = "None"
                tag_tag = "None"
                date_rel = "None"
                date_tag = "None"
            else:
                # Check for changes
                last_tag = versions.get(repo_name, {}).get('tag')
                last_rel = versions.get(repo_name, {}).get('release')
                
                if last_tag and last_tag != tag_tag:
                    changes = True
                    changes_count += 1
                    console.print(f"[bold green]{counter} NEW: {repo_name}[/bold green]")
                elif verbose:
                    console.print(f"[dim]{counter} No changes: {repo_name}[/dim]")
                
                date_rel = find(req_rel, "relative-time") if req_rel else "Unknown"
                date_tag = find(req_tag, "relative-time") if req_tag else "Unknown"
                
                new_versions[repo_name] = {
                    'release': tag_rel,
                    'tag': tag_tag,
                    'date_rel': date_rel,
                    'date_tag': date_tag,
                }
            
            # Format table values
            table_new = "[bold green]NEW[/bold green]" if changes else ""
            table_rel = f"[bold green]{tag_rel}[/bold green]" if changes else tag_rel
            table_tag = f"[bold green]{tag_tag}[/bold green]" if changes else tag_tag
            table_date_rel = f"[bold green]{date_rel}[/bold green]" if changes else date_rel
            table_date_tag = f"[bold green]{date_tag}[/bold green]" if changes else date_tag
            
            rows.append([
                f"#{i}",
                f"[link={repo_url}]{repo_name}[/link] {table_new}",
                table_rel,
                table_date_rel,
                table_tag,
                table_date_tag,
            ])
            
            time.sleep(wait)
    
    # Print table
    for row in rows:
        table.add_row(*row)
    console.print(table)
    
    # Summary
    elapsed = time.time() - start
    console.print(f"\n[bold]{changes_count} new releases found![/bold]")
    console.print(f"[dim]Completed in {elapsed:.2f}s[/dim]")
    
    # Save if changes detected
    if changes_count > 0:
        save = typer.confirm("Save updated versions?", default=True)
        if save:
            save_versions(new_versions)
            console.print("[bold green]✅ Versions saved![/bold green]")


@app.command()
def list():
    """List all repos in repos.json."""
    repos = load_repos()
    
    table = Table(title="Repos in repos.json")
    table.add_column("Name")
    table.add_column("URL")
    
    for name, url in repos.items():
        table.add_row(name, url)
    
    console.print(table)


@app.command()
def add(
    url: str = typer.Option(..., "-u", "--url", help="GitHub repo URL"),
    name: Optional[str] = typer.Option(None, "-n", "--name", help="Custom repo name (optional)"),
):
    """Add a new repo."""
    repos = load_repos()
    
    # Clean URL
    if url.endswith('/'):
        url = url[:-1]
    
    # Extract author/repo
    parts = url.split('/')
    author = parts[-2]
    repo = parts[-1]
    
    if not author or not repo:
        console.print("[bold red]Invalid URL![/bold red]")
        raise typer.Exit(code=1)
    
    # Use custom name or auto-generate
    repo_name = name or f"{author}/{repo}"
    
    if repo_name in repos:
        console.print(f"[bold yellow]Repo '{repo_name}' already exists![/bold yellow]")
        raise typer.Exit(code=1)
    
    repos[repo_name] = url
    save_repos(repos)
    console.print(f"[bold green]✅ Added repo: {repo_name}[/bold green]")


@app.command()
def remove(
    name: str = typer.Option(..., "-n", "--name", help="Repo name to remove"),
):
    """Remove a repo."""
    repos = load_repos()
    
    if name not in repos:
        console.print(f"[bold red]Repo '{name}' not found![/bold red]")
        raise typer.Exit(code=1)
    
    confirm = typer.confirm(f"Delete '{name}'?", default=False)
    if confirm:
        del repos[name]
        save_repos(repos)
        console.print(f"[bold green]✅ Removed repo: {name}[/bold green]")


@app.command()
def version():
    """Show version."""
    console.print(f"[bold]GitHub Watcher[/bold] v{SCRIPT_VERSION}")


if __name__ == "__main__":
    app()