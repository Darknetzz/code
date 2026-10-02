# rust-sizetree

Disk space analyzer (scan + report + native GUI). Rust port of the legacy Python tool in `Python/pytree/`.

TreeSize-like recursive directory scanning with CLI table/tree output, interactive HTML reports, and an egui desktop window with a live-updating size tree.

## Build

```powershell
cd Rust/rust-sizetree
cargo build --release
```

The PATH symlink `rust-sizetree` points at `target/release/rust-sizetree.exe`, so a release build updates the command on PATH.

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

# Native GUI (live tree while scanning)
cargo run --release -- gui .
cargo run --release -- gui D:\Kriss\Videos --hidden
rust-sizetree gui D:\Kriss\Videos
```

## Commands

| Command | Description |
|---------|-------------|
| `scan` | Terminal table or tree view (`-d` depth, `-l` limit, `-t` tree, `--hidden`) |
| `report` | HTML/JSON/Markdown/text report (`-o`, `--format`, `--no-open`, same scan flags) |
| `gui` | Native SizeTree window (live tree, filters, free space, open in Explorer) |
| `version` | Show version |

## GUI

`gui` opens a desktop window:

- Toolbar: path, Browse, Rescan, Cancel, **Report** menu, **Options…**, show hidden, max depth, name filter
- Report: **HTML (open)** writes a temp HTML report from the current scan and opens it; **Save as…** picks a path (format from extension or Options default)
- Options: toggle visible columns (Share / Size / % / Files / Dirs; Name always on) and report defaults (format, child limit, open HTML after save) — prefs persist across launches
- Live tree: folders appear as they are entered; sizes grow until each folder completes
- Status: files/dirs/size, current path, volume used/free
- Details: child size bars, Open in Explorer, Copy path

Cancel keeps the partial tree (and reports can export that partial data). Name filter is display-only; hidden/depth apply on the next scan.

## HTML reports

`report` without `-o` writes `rust-sizetree-<folder>-<timestamp>.html` under your temp directory and opens it in the default browser (use `--no-open` to skip). HTML matches the pytree interactive report: storage overview chart, expandable folder tree, column sort, name filter, and heat-map size pills.

> **Legacy / reference:** Textual TUI (`pytree tui`) remains in `Python/pytree/`.
