# pycrawl

Universal, reusable web crawler for downloading files (e.g. PDFs) from index pages. Built with **Typer** and **Rich**.

## Install

```bash
pip install -r requirements.txt
```

## Usage

Crawl a URL and download matching files. You must pass the start URL and can optionally follow links that match a regex.

```bash
# Only the start page: download PDFs into downloads/
python pycrawl.py run "https://example.com/docs" -o ./downloads

# Follow links matching a regex, then download PDFs from each page
python pycrawl.py run "https://example.com/index" -f "example.com/section/" -e pdf -o ./out

# Multiple extensions
python pycrawl.py run "https://example.com/files" --extensions "pdf,zip" -o ./out
```

List all file URLs that would be downloaded (no download):

```bash
python pycrawl.py list-urls "https://example.com/docs" -f "example.com/section/"
```

### Options

- **URL** (required): Start URL to crawl.
- **`--out` / `-o`**: Output directory (default: `downloads`).
- **`--follow` / `-f`**: Regex for links to crawl as subpages. Omit to only use the start URL.
- **`--extensions` / `-e`**: Comma-separated extensions (default: `pdf`).
- **`--delay` / `-d`**: Seconds between requests (default: 0.5).
- **`--overwrite`**: Re-download and overwrite existing files.

## Reusing the crawler in code

Import and use the core functions:

```python
from pathlib import Path
from pycrawl import crawl_and_download, _make_session

followed, downloaded, failed = crawl_and_download(
    "https://example.com/docs",
    Path("downloads"),
    session=_make_session(),
    follow_pattern=r"example\.com/section/",
    extensions=(".pdf",),
    delay_sec=0.5,
    subdir_from_url=lambda url: "section-1" if "section-1" in url else "",  # optional
)
```

Functions like `fetch_html`, `extract_links`, and `download_file` are also public and reusable for custom pipelines.
