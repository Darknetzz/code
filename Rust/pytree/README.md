# pytree

Rust port of the **scan** and **report** commands from `Python/pytree/`. Interactive TUI (`pytree tui`) remains Python-only (Textual).

TreeSize-like disk space analyzer: recursive directory scanning with CLI table/tree output and HTML/JSON/Markdown/text reports.

## Build

```powershell
cd Rust/pytree
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
