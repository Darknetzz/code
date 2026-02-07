"""
Universal, reusable web crawler for downloading files (e.g. PDFs) from index pages.
Uses Typer + Rich. Supports custom start URL, link patterns, and file types.
"""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests
import typer
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

# ---------------------------------------------------------------------------
# Defaults and constants
# ---------------------------------------------------------------------------

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"
)
DEFAULT_DELAY_SEC = 0.5
DEFAULT_EXTENSIONS = (".pdf",)
CDX_API = "https://web.archive.org/cdx/search/cdx"
WAYBACK_BASE = "https://web.archive.org/web"

# ---------------------------------------------------------------------------
# Reusable crawler core
# ---------------------------------------------------------------------------


def _make_session(
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: int = 30,
) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": user_agent})
    s.timeout = timeout
    return s


def fetch_html(session: requests.Session, url: str) -> str | None:
    """Fetch a URL and return response text, or None on failure."""
    try:
        r = session.get(url)
        r.raise_for_status()
        return r.text
    except requests.RequestException:
        return None


def extract_links(
    html: str,
    base_url: str,
    *,
    follow_pattern: str | re.Pattern | None = None,
    extension_filter: tuple[str, ...] = DEFAULT_EXTENSIONS,
    only_download_pattern: str | re.Pattern | None = None,
) -> tuple[list[str], list[str]]:
    """
    Parse HTML and return (links_to_follow, links_to_download).
    - follow_pattern: regex (as str or compiled) for href to treat as subpages to crawl.
    - extension_filter: only consider hrefs whose path ends with one of these (e.g. .pdf).
    - only_download_pattern: if set, download links must also match this regex.
    """
    soup = BeautifulSoup(html, "html.parser")
    to_follow: list[str] = []
    to_download: list[str] = []

    follow_re = re.compile(follow_pattern) if isinstance(follow_pattern, str) else follow_pattern
    download_re = (
        re.compile(only_download_pattern)
        if isinstance(only_download_pattern, str)
        else only_download_pattern
    )

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        path_lower = (parsed.path or "").lower()

        if follow_re and follow_re.search(full):
            to_follow.append(full)
            continue
        if not any(path_lower.endswith(ext.lower()) for ext in extension_filter):
            continue
        if download_re and not download_re.search(full):
            continue
        to_download.append(full)

    return (list(dict.fromkeys(to_follow)), list(dict.fromkeys(to_download)))


def filename_from_url(url: str) -> str:
    """Last path segment, or 'index' if empty."""
    path = urlparse(url).path.rstrip("/")
    return path.split("/")[-1] or "index"


def subdir_from_page_url(page_url: str) -> str:
    """Default subdir name from a page URL: last path segment (for grouping by section)."""
    path = urlparse(page_url).path.rstrip("/")
    return path.split("/")[-1] or "index"


# Magic bytes for response validation (only when extension is known)
_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK"


def _response_matches_extension(ext: str, content_type: str | None, first_bytes: bytes) -> bool:
    """True if the response looks like the given file extension."""
    ext = ext.lower()
    if ext == ".pdf":
        if first_bytes.startswith(_PDF_MAGIC):
            return True
        if content_type:
            ct = content_type.split(";")[0].strip().lower()
            if ct in ("application/pdf", "application/octet-stream"):
                return True
        return False
    if ext == ".zip":
        return first_bytes.startswith(_ZIP_MAGIC)
    # Unknown extension: no validation
    return True


def download_file(
    session: requests.Session,
    url: str,
    dest_path: Path,
    *,
    overwrite: bool = False,
    expected_extension: str | None = None,
) -> bool:
    """Stream download url to dest_path. Returns True on success.
    When expected_extension is .pdf or .zip, refuses to save if the response
    does not match that type (e.g. HTML gate). Other extensions are not validated."""
    if dest_path.exists() and not overwrite:
        return True
    try:
        r = session.get(url, stream=True)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type")
        first_chunk = next(r.iter_content(chunk_size=8192), None) or b""
        if expected_extension and not _response_matches_extension(
            expected_extension, content_type, first_chunk
        ):
            return False
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(first_chunk)
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return True
    except (requests.RequestException, OSError):
        return False


# ---------------------------------------------------------------------------
# Wayback Machine (web.archive.org) helpers
# ---------------------------------------------------------------------------


def get_wayback_first_timestamp(
    session: requests.Session,
    url: str,
    from_date: str,
    *,
    delay_sec: float = 0.3,
) -> str | None:
    """
    Query CDX API for the first (oldest) capture of url on or after from_date.
    from_date: YYYYMMDD. Returns timestamp (14 chars) or None.
    """
    try:
        params = {
            "url": url,
            "from": from_date,
            "output": "json",
            "limit": "1",
            "reverse": "1",  # ascending time -> first capture
        }
        r = session.get(CDX_API, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not data or len(data) < 2:
            return None
        # Row 0 = header, row 1 = first record. Columns: urlkey, timestamp, original, ...
        row = data[1]
        if len(row) < 2:
            return None
        return row[1]
    except (requests.RequestException, ValueError, IndexError):
        return None
    finally:
        time.sleep(delay_sec)


def wayback_download_url(original_url: str, timestamp: str) -> str:
    """Build Wayback URL for raw document (identity, not wrapper)."""
    return f"{WAYBACK_BASE}/{timestamp}id_/{original_url}"


def _set_file_mtime_from_wayback_timestamp(path: Path, timestamp: str) -> None:
    """Set file modification (and access) time from Wayback timestamp (YYYYMMDDhhmmss)."""
    if len(timestamp) < 14:
        return
    try:
        dt = datetime.strptime(timestamp[:14], "%Y%m%d%H%M%S")
        mtime = dt.timestamp()
        os.utime(path, (mtime, mtime))
    except (ValueError, OSError):
        pass


def _normalize_subdir(subdir: str) -> str:
    return subdir.strip("/").replace("/", os.sep)


def crawl_and_download(
    start_url: str,
    out_dir: Path,
    *,
    session: requests.Session | None = None,
    follow_pattern: str | re.Pattern | None = None,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    only_download_pattern: str | re.Pattern | None = None,
    delay_sec: float = DEFAULT_DELAY_SEC,
    overwrite: bool = False,
    subdir_from_url: Callable[[str], str] | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """
    Crawl from start_url; optionally follow links matching follow_pattern,
    collect asset links by extension, then download into out_dir.
    Returns (followed_pages, downloaded_urls, failed_urls).
    """
    session = session or _make_session()
    followed: list[str] = []
    downloaded: list[str] = []
    failed: list[str] = []

    pages_to_process: list[str] = [start_url]
    if follow_pattern:
        html = fetch_html(session, start_url)
        if html:
            to_follow, _ = extract_links(
                html,
                start_url,
                follow_pattern=follow_pattern,
                extension_filter=(),
            )
            pages_to_process.extend(to_follow)
        time.sleep(delay_sec)

    to_download: list[tuple[str, str]] = []
    for page_url in pages_to_process:
        if page_url != start_url:
            time.sleep(delay_sec)
        html = fetch_html(session, page_url)
        if not html:
            continue
        _, page_assets = extract_links(
            html,
            page_url,
            follow_pattern=follow_pattern,
            extension_filter=extensions,
            only_download_pattern=only_download_pattern,
        )
        for asset_url in page_assets:
            to_download.append((page_url, asset_url))
        followed.append(page_url)

    seen = set()
    unique_downloads: list[tuple[str, str]] = []
    for page_url, asset_url in to_download:
        if asset_url not in seen:
            seen.add(asset_url)
            unique_downloads.append((page_url, asset_url))

    total = len(unique_downloads)
    for idx, (page_url, asset_url) in enumerate(unique_downloads, 1):
        if on_progress:
            on_progress(asset_url, idx, total)
        subdir = (subdir_from_url(page_url) or "").strip() if subdir_from_url else ""
        name = filename_from_url(asset_url)
        ext = Path(name).suffix.lower() or None
        if subdir:
            dest = out_dir / _normalize_subdir(subdir) / name
        else:
            dest = out_dir / name
        if download_file(
            session, asset_url, dest, overwrite=overwrite, expected_extension=ext
        ):
            downloaded.append(asset_url)
        else:
            failed.append(asset_url)
        time.sleep(delay_sec)

    return (followed, downloaded, failed)


def crawl_and_download_wayback(
    start_url: str,
    wayback_out_dir: Path,
    from_date: str,
    *,
    session: requests.Session | None = None,
    follow_pattern: str | re.Pattern | None = None,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    only_download_pattern: str | re.Pattern | None = None,
    delay_sec: float = DEFAULT_DELAY_SEC,
    cdx_delay_sec: float = 0.3,
    overwrite: bool = False,
    subdir_from_url: Callable[[str], str] | None = None,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """
    Discover file URLs from the live start_url (same as crawl_and_download), then
    download the first Wayback Machine capture on or after from_date (YYYYMMDD)
    for each file into wayback_out_dir. Use this to compare with current scrapes.
    Returns (followed_pages, downloaded_urls, failed_urls).
    """
    session = session or _make_session()
    followed: list[str] = []
    downloaded: list[str] = []
    failed: list[str] = []

    pages_to_process: list[str] = [start_url]
    if follow_pattern:
        html = fetch_html(session, start_url)
        if html:
            to_follow, _ = extract_links(
                html,
                start_url,
                follow_pattern=follow_pattern,
                extension_filter=(),
            )
            pages_to_process.extend(to_follow)
        time.sleep(delay_sec)

    to_download: list[tuple[str, str]] = []
    for page_url in pages_to_process:
        if page_url != start_url:
            time.sleep(delay_sec)
        html = fetch_html(session, page_url)
        if not html:
            continue
        _, page_assets = extract_links(
            html,
            page_url,
            follow_pattern=follow_pattern,
            extension_filter=extensions,
            only_download_pattern=only_download_pattern,
        )
        for asset_url in page_assets:
            to_download.append((page_url, asset_url))
        followed.append(page_url)

    seen = set()
    unique_downloads: list[tuple[str, str]] = []
    for page_url, asset_url in to_download:
        if asset_url not in seen:
            seen.add(asset_url)
            unique_downloads.append((page_url, asset_url))

    total = len(unique_downloads)
    for idx, (page_url, asset_url) in enumerate(unique_downloads, 1):
        if on_progress:
            on_progress(asset_url, idx, total)
        timestamp = get_wayback_first_timestamp(
            session, asset_url, from_date, delay_sec=cdx_delay_sec
        )
        if not timestamp:
            failed.append(asset_url)
            time.sleep(delay_sec)
            continue
        wayback_url = wayback_download_url(asset_url, timestamp)
        subdir = (subdir_from_url(page_url) or "").strip() if subdir_from_url else ""
        name = filename_from_url(asset_url)
        ext = Path(name).suffix.lower() or None
        if subdir:
            dest = wayback_out_dir / _normalize_subdir(subdir) / name
        else:
            dest = wayback_out_dir / name
        if download_file(
            session, wayback_url, dest, overwrite=overwrite, expected_extension=ext
        ):
            downloaded.append(asset_url)
            _set_file_mtime_from_wayback_timestamp(dest, timestamp)
        else:
            failed.append(asset_url)
        time.sleep(delay_sec)

    return (followed, downloaded, failed)


# ---------------------------------------------------------------------------
# CLI (Typer + Rich)
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="pycrawl",
    help="Universal crawler to download files (e.g. PDFs) from index pages.",
    no_args_is_help=True,
)
console = Console()


@app.command("run")
def run(
    url: str = typer.Argument(
        ...,
        help="Start URL to crawl (index page that links to sections and/or files).",
    ),
    out: Path = typer.Option(
        Path("downloads"),
        "--out",
        "-o",
        path_type=Path,
        help="Output directory for downloaded files.",
    ),
    follow: str | None = typer.Option(
        None,
        "--follow",
        "-f",
        help="Regex for links to follow as subpages. Omit to only use the start URL.",
    ),
    extensions: str = typer.Option(
        "pdf",
        "--extensions",
        "-e",
        help="Comma-separated file extensions to download (e.g. pdf,zip).",
    ),
    delay: float = typer.Option(
        DEFAULT_DELAY_SEC,
        "--delay",
        "-d",
        help="Seconds to wait between requests.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Re-download and overwrite existing files.",
    ),
    no_subdirs: bool = typer.Option(
        False,
        "--no-subdirs",
        "--flat",
        help="Put all files in the output directory; do not create subdirs per page.",
    ),
    cookie: str | None = typer.Option(
        None,
        "--cookie",
        "-c",
        help="Cookie header (e.g. from browser after passing age gate). Enables PDF downloads on gated sites.",
    ),
    wayback_from: str | None = typer.Option(
        None,
        "--wayback-from",
        help="Scrape from Wayback Machine: first capture on or after this date (YYYYMMDD). Saves to --wayback-out for comparison with current files.",
    ),
    wayback_out: Path | None = typer.Option(
        None,
        "--wayback-out",
        path_type=Path,
        help="Output directory for Wayback scrapes (used with --wayback-from). Default: <out>_wayback.",
    ),
):
    """
    Crawl a URL and download matching files (e.g. PDFs).
    Use --follow to crawl subpages that match a regex before collecting file links.
    When --follow is set, files are grouped into subdirs by page by default; use
    --no-subdirs to save everything in the output directory.
    For .pdf and .zip, responses are checked for correct magic bytes; wrong type
    (e.g. HTML gate) is counted as failed. Use --cookie if the site requires verification.
    Use --wayback-from YYYYMMDD to download the first archived version from web.archive.org
    into a separate directory (--wayback-out) so you can compare with current scrapes.

    Examples:

      pycrawl run https://example.com/docs -o ./downloads

      pycrawl run https://example.com/index -f "example.com/section/" -e pdf

      pycrawl run https://example.com/files --extensions "pdf,zip" --overwrite

      pycrawl run https://example.com/index -f "section/" --no-subdirs -o ./flat

      pycrawl run https://example.com/docs -o ./current --wayback-from 20250101 --wayback-out ./archive
    """
    if wayback_from and not re.match(r"^\d{8}$", wayback_from):
        console.print("[red]--wayback-from must be YYYYMMDD (e.g. 20250101)[/red]")
        raise typer.Exit(1)

    ext_tuple = tuple("." + x.strip().lstrip(".") for x in extensions.split(",") if x.strip())
    if not ext_tuple:
        ext_tuple = DEFAULT_EXTENSIONS

    follow_pattern: str | re.Pattern | None = re.compile(follow) if follow else None
    use_subdirs = follow_pattern and not no_subdirs
    subdir_from_url_cb: Callable[[str], str] | None = subdir_from_page_url if use_subdirs else None

    session = _make_session()
    if cookie:
        session.headers["Cookie"] = cookie.strip()

    use_wayback = wayback_from is not None
    if use_wayback:
        wayback_out_dir = (wayback_out or (out.parent / (out.name + "_wayback"))).resolve()
        wayback_out_dir.mkdir(parents=True, exist_ok=True)

    time_started = datetime.now()

    # Rich can fail in PyInstaller/frozen builds (missing rich._unicode_data.unicode17-0-0)
    use_rich = True
    try:
        _progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        )
        with _progress:
            _tid = _progress.add_task("Test", total=1)
            _progress.update(_tid, description="Test", completed=1, total=1)
    except Exception:
        use_rich = False

    downloaded_list: list[str] = []
    failed_list: list[str] = []

    if use_rich:
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        )
        with progress:
            task_id = progress.add_task(
                "Wayback crawl..." if use_wayback else "Crawling and downloading...",
                total=None,
            )

            def on_progress(asset_url: str, cur: int, tot: int) -> None:
                progress.update(
                    task_id,
                    description=f"[{cur}/{tot}] {filename_from_url(asset_url)}",
                    total=tot,
                    completed=cur,
                )

            if use_wayback:
                followed_pages, downloaded_list, failed_list = crawl_and_download_wayback(
                    url,
                    wayback_out_dir,
                    wayback_from,
                    session=session,
                    follow_pattern=follow_pattern,
                    extensions=ext_tuple,
                    delay_sec=delay,
                    overwrite=overwrite,
                    subdir_from_url=subdir_from_url_cb,
                    on_progress=on_progress,
                )
            else:
                followed_pages, downloaded_list, failed_list = crawl_and_download(
                    url,
                    out,
                    session=session,
                    follow_pattern=follow_pattern,
                    extensions=ext_tuple,
                    delay_sec=delay,
                    overwrite=overwrite,
                    subdir_from_url=subdir_from_url_cb,
                    on_progress=on_progress,
                )
    else:
        def on_progress(asset_url: str, cur: int, tot: int) -> None:
            print(f"  [{cur}/{tot}] {filename_from_url(asset_url)}", flush=True)

        if use_wayback:
            followed_pages, downloaded_list, failed_list = crawl_and_download_wayback(
                url,
                wayback_out_dir,
                wayback_from,
                session=session,
                follow_pattern=follow_pattern,
                extensions=ext_tuple,
                delay_sec=delay,
                overwrite=overwrite,
                subdir_from_url=subdir_from_url_cb,
                on_progress=on_progress,
            )
        else:
            followed_pages, downloaded_list, failed_list = crawl_and_download(
                url,
                out,
                session=session,
                follow_pattern=follow_pattern,
                extensions=ext_tuple,
                delay_sec=delay,
                overwrite=overwrite,
                subdir_from_url=subdir_from_url_cb,
                on_progress=on_progress,
            )

    time_completed = datetime.now()
    elapsed = time_completed - time_started
    elapsed_str = str(elapsed).split(".")[0] if elapsed.total_seconds() >= 1 else f"{elapsed.total_seconds():.2f}s"

    # Summary
    if use_rich:
        try:
            table = Table(title="Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Count", justify="right", style="green")
            table.add_row("Pages crawled", str(len(followed_pages)))
            table.add_row("Files downloaded", str(len(downloaded_list)))
            table.add_row("Failed", str(len(failed_list)))
            table.add_row("Time started", time_started.strftime("%Y-%m-%d %H:%M:%S"))
            table.add_row("Time completed", time_completed.strftime("%Y-%m-%d %H:%M:%S"))
            table.add_row("Time elapsed", elapsed_str)
            if use_wayback:
                table.add_row("Saved to", str(wayback_out_dir))
            console.print(
                Panel(
                    table,
                    title="Wayback crawl complete" if use_wayback else "Crawl complete",
                    border_style="green",
                )
            )
            if failed_list:
                console.print("[red]Failed URLs (first 10):[/]")
                for u in failed_list[:10]:
                    console.print(f"  {u}")
                if len(failed_list) > 10:
                    console.print(f"  ... and {len(failed_list) - 10} more.")
        except Exception:
            use_rich = False
    if not use_rich:
        print(f"Pages crawled: {len(followed_pages)}")
        print(f"Files downloaded: {len(downloaded_list)}")
        print(f"Failed: {len(failed_list)}")
        print(f"Time started: {time_started.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Time completed: {time_completed.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Time elapsed: {elapsed_str}")
        if use_wayback:
            print(f"Saved to: {wayback_out_dir}")
        if failed_list:
            print("Failed URLs (first 10):")
            for u in failed_list[:10]:
                print(f"  {u}")
            if len(failed_list) > 10:
                print(f"  ... and {len(failed_list) - 10} more.")


@app.command("list-urls")
def list_urls(
    url: str = typer.Argument(
        ...,
        help="URL to crawl and list (no download).",
    ),
    follow: str | None = typer.Option(
        None,
        "--follow",
        "-f",
        help="Regex for links to follow.",
    ),
    extensions: str = typer.Option(
        "pdf",
        "--extensions",
        "-e",
        help="Comma-separated extensions to list.",
    ),
):
    """
    List all file URLs that would be downloaded (dry run).

    Examples:

      pycrawl list-urls https://example.com/docs

      pycrawl list-urls https://example.com/index -f "example.com/section/" -e pdf
    """
    ext_tuple = tuple("." + x.strip().lstrip(".") for x in extensions.split(",") if x.strip()) or DEFAULT_EXTENSIONS
    follow_pattern = follow or None
    session = _make_session()
    pages = [url]
    if follow_pattern:
        html = fetch_html(session, url)
        if html:
            to_follow, _ = extract_links(html, url, follow_pattern=follow_pattern, extension_filter=())
            pages.extend(to_follow)
    all_assets: list[str] = []
    for page_url in pages:
        time.sleep(0.3)
        html = fetch_html(session, page_url)
        if html:
            _, assets = extract_links(
                html,
                page_url,
                follow_pattern=follow_pattern,
                extension_filter=ext_tuple,
            )
            all_assets.extend(assets)
    seen = set()
    for u in all_assets:
        if u not in seen:
            seen.add(u)
            console.print(u)


if __name__ == "__main__":
    app()
