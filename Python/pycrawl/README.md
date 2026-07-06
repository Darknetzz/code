# pycrawl

> **Legacy / reference implementation.** The canonical crawler is the Rust port in [`Rust/pycrawl`](../../Rust/pycrawl/). This Python version remains for PyInstaller builds and programmatic import.

Universal, reusable web crawler for downloading files (e.g. PDFs) from index pages. Built with **Typer** and **Rich**. Crawl a start URL, optionally follow links matching a regex, collect asset links by file extension, and download them—with progress display and subdirectory grouping.

## Features

- **Single-page or multi-page crawl** — Use only the start URL or follow subpages that match a regex
- **Flexible file types** — Download PDFs, ZIPs, or any extension via comma-separated list
- **Subdirectory grouping** — Files grouped by source page when following links
- **Dry run** — List URLs without downloading
- **Programmatic API** — Use core functions in your own scripts

## Installation

```bash
pip install -r requirements.txt
```

Or install dependencies directly:

```bash
pip install typer[all] rich requests beautifulsoup4
```

## Quick Start

```bash
# Download PDFs from a single page into ./downloads
pycrawl run https://example.com/docs -o ./downloads

# Crawl subpages and download PDFs from each
pycrawl run https://example.com/docs -f "example.com/section/" -o ./downloads

# List URLs only (no download)
pycrawl list-urls https://example.com/docs
```

## Commands

| Command      | Description                                      |
|-------------|---------------------------------------------------|
| `run`       | Crawl URL(s) and download matching files          |
| `list-urls` | Crawl URL(s) and print file URLs (no download)    |

---

## `run` — Crawl and Download

Crawl a start URL, optionally follow links that match a regex, collect file links by extension, and download them.

### Synopsis

```bash
pycrawl run URL [OPTIONS]
```

### Arguments & Options

| Option | Short | Default    | Description                                                                 |
|--------|-------|------------|-----------------------------------------------------------------------------|
| `URL`  | —     | *(required)* | Start URL to crawl (index page that links to sections and/or files)         |
| `--out` | `-o`  | `downloads` | Output directory for downloaded files                                       |
| `--follow` | `-f` | —          | Regex for links to follow as subpages. Omit to only crawl the start URL     |
| `--extensions` | `-e` | `pdf`    | Comma-separated extensions to download (e.g. `pdf`, `pdf,zip`)               |
| `--delay` | `-d`  | `0.5`     | Seconds to wait between requests                                            |
| `--overwrite` | —   | `false`   | Re-download and overwrite existing files                                    |
| `--no-subdirs` | `--flat` | `false` | Put all files in output dir; do not create subdirs per page                 |

### How It Works

1. **Without `--follow`**: Fetches only the start URL and downloads all links whose path ends with one of the given extensions.
2. **With `--follow`**: First fetches the start URL, collects links matching the regex as “subpages,” then fetches each subpage and collects file links from all of them. Files are grouped into subdirectories by the page they were found on (unless `--no-subdirs` is used).

### Examples

#### 1. Single page — download PDFs only

```bash
pycrawl run https://example.com/docs -o ./downloads
```

Downloads all PDF links from `https://example.com/docs` into `./downloads/`.

---

#### 2. Crawl subpages and download PDFs

```bash
pycrawl run https://example.com/manual -f "example.com/manual/chapter" -o ./manual
```

- Fetches `https://example.com/manual`
- Follows links matching `example.com/manual/chapter` (e.g. `chapter-1`, `chapter-2`)
- Collects PDF links from each page
- Saves into `./manual/chapter-1/file.pdf`, `./manual/chapter-2/file.pdf`, etc.

---

#### 3. Download multiple file types

```bash
pycrawl run https://example.com/resources --extensions "pdf,zip,tar.gz" -o ./resources
```

Downloads links ending in `.pdf`, `.zip`, or `.tar.gz`.

---

#### 4. Flat output — all files in one directory

```bash
pycrawl run https://example.com/manual -f "example.com/manual/chapter" --no-subdirs -o ./flat
```

Same crawl as in example 2, but all files go directly into `./flat/` with no subdirectories.

---

#### 5. Overwrite existing files

```bash
pycrawl run https://example.com/docs -o ./downloads --overwrite
```

Re-downloads files even if they already exist locally.

---

#### 6. Slower crawl (polite delay)

```bash
pycrawl run https://example.com/docs -o ./downloads --delay 1.5
```

Waits 1.5 seconds between each request.

---

#### 7. Follow pattern — practical regex tips

```bash
# Match URLs containing "section" or "part"
pycrawl run https://example.com/index -f "section|part" -o ./out

# Match URLs with a numeric chapter ID
pycrawl run https://example.com/book -f "chapter-[0-9]+" -o ./book

# Match only links under /docs/
pycrawl run https://example.com -f "example\.com/docs/" -o ./docs
```

---

## `list-urls` — Dry Run

Crawl the same way as `run`, but only print the file URLs instead of downloading. Useful for inspecting what would be downloaded.

### Synopsis

```bash
pycrawl list-urls URL [OPTIONS]
```

### Arguments & Options

| Option | Short | Default | Description                                   |
|--------|-------|---------|-----------------------------------------------|
| `URL`  | —     | *(required)* | Start URL to crawl                         |
| `--follow` | `-f` | —       | Regex for links to follow as subpages         |
| `--extensions` | `-e` | `pdf` | Comma-separated extensions to list            |

### Examples

```bash
# List PDF URLs from a single page
pycrawl list-urls https://example.com/docs

# List PDF URLs after following section links
pycrawl list-urls https://example.com/index -f "example.com/section/" -e pdf

# List ZIP and PDF URLs
pycrawl list-urls https://example.com/files --extensions "zip,pdf"
```

Output (one URL per line):

```
https://example.com/docs/file1.pdf
https://example.com/docs/file2.pdf
```

---

## Reusing in Code

Import and use the core functions for custom pipelines:

```python
from pathlib import Path
from pycrawl import crawl_and_download, _make_session

followed, downloaded, failed = crawl_and_download(
    "https://example.com/docs",
    Path("downloads"),
    session=_make_session(),
    follow_pattern=r"example\.com/section/",
    extensions=(".pdf", ".zip"),
    delay_sec=0.5,
    overwrite=False,
    subdir_from_url=lambda url: "custom-folder" if "special" in url else "",
)

print(f"Crawled {len(followed)} pages, downloaded {len(downloaded)} files, {len(failed)} failed")
```

### Available Functions

| Function | Description |
|----------|-------------|
| `_make_session()` | Create a `requests.Session` with User-Agent and timeout |
| `fetch_html(session, url)` | Fetch URL, return HTML text or `None` |
| `extract_links(html, base_url, follow_pattern=..., extension_filter=..., only_download_pattern=...)` | Parse HTML, return `(links_to_follow, links_to_download)` |
| `download_file(session, url, dest_path, overwrite=False)` | Stream-download URL to path, return success |
| `crawl_and_download(...)` | Full crawl-and-download pipeline, returns `(followed, downloaded, failed)` |

---

## Summary

- Use `run` to crawl and download; use `list-urls` to inspect URLs only.
- `--follow` enables multi-page crawl; omit it for single-page.
- Use `--no-subdirs` / `--flat` to put all files in one directory.
- The crawler is polite by default (0.5 s delay); increase with `--delay` if needed.
