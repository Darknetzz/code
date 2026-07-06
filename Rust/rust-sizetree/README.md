# rust-sizetree

Disk space analyzer (scan + report). Rust port of the legacy Python tool in `Python/pytree/`. Interactive TUI (`pytree tui`) remains Python-only (Textual).

TreeSize-like recursive directory scanning with CLI table/tree output and interactive HTML reports (expandable tree table, donut/stacked-bar viz, sort, filter).

## Build

```powershell
cd Rust/rust-sizetree
cargo build --release
```

## Usage

```powershell
# Terminal scan (with live progress on stderr)
cargo run --release -- scan .
cargo run --release -- scan C:\Users -d 2 -l 30 -t
cargo run --release -- scan . --hidden

# Reports — defaults to HTML in %TEMP%, opens browser
cargo run --release -- report .
cargo run --release -- report . --no-open -o sizes.html
cargo run --release -- report . --format json -o out.json
cargo run --release -- report . --format markdown -o out.md -t
```

## Commands

| Command | Description |
|---------|-------------|
| `scan` | Terminal table or tree view (`-d` depth, `-l` limit, `-t` tree, `--hidden`) |
| `report` | HTML/JSON/Markdown/text report (`-o`, `--format`, `--no-open`, same scan flags) |
| `version` | Show version |

## HTML reports

`report` without `-o` writes `rust-sizetree-<folder>-<timestamp>.html` under your temp directory and opens it in the default browser (use `--no-open` to skip). HTML matches the pytree interactive report: storage overview chart, expandable folder tree, column sort, name filter, and heat-map size pills.

> **Legacy / reference:** Textual TUI (`pytree tui`) remains in `Python/pytree/`.
