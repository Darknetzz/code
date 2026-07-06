# pycrawl

Rust port of the Python web crawler in `Python/pycrawl/`.

Crawl a start URL, optionally follow links matching a regex, collect asset links by extension, and download them.

## Build

```powershell
cd Rust/pycrawl
cargo build --release
```

## Usage

```powershell
cargo run --release -- run https://example.com/docs -o ./downloads
cargo run --release -- run https://example.com/index -f "example.com/section/" -e pdf
cargo run --release -- list-urls https://example.com/docs
cargo run --release -- run https://example.com/docs -o ./current --wayback-from 20250101 --wayback-out ./archive
```

## Commands

| Command | Description |
|---------|-------------|
| `run` | Crawl and download matching files |
| `list-urls` | Dry run — print URLs only |

## Options (`run`)

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --out` | `downloads` | Output directory |
| `-f, --follow` | — | Regex for subpages to crawl |
| `-e, --extensions` | `pdf` | Comma-separated extensions |
| `-d, --delay` | `0.5` | Seconds between requests |
| `--overwrite` | off | Re-download existing files |
| `--no-subdirs` / `--flat` | off | Flat output layout |
| `-c, --cookie` | — | Cookie header for gated sites |
| `--wayback-from` | — | Wayback scrape from YYYYMMDD |
| `--wayback-out` | `<out>_wayback` | Wayback output directory |

> **Legacy / reference:** The Python implementation in `Python/pycrawl/` remains available for PyInstaller builds and programmatic use.
