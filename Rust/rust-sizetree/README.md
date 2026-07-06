# rust-sizetree

Disk space analyzer (scan + report). Rust port of the legacy Python tool in `Python/pytree/`. Interactive TUI (`pytree tui`) remains Python-only (Textual).

TreeSize-like recursive directory scanning with CLI table/tree output and HTML/JSON/Markdown/text reports.

## Build

```powershell
cd Rust/rust-sizetree
cargo build --release
```

## Usage

```powershell
cargo run --release -- scan .
cargo run --release -- scan C:\Users -d 2 -l 30 -t
cargo run --release -- report . -o sizes.html
cargo run --release -- report . --format json -o out.json
```

## Commands

| Command | Description |
|---------|-------------|
| `scan` | Terminal table or tree view |
| `report` | Write HTML/JSON/Markdown/text report |
| `version` | Show version |

> **Legacy / reference:** Full TUI and advanced HTML visualizations remain in `Python/pytree/`.
