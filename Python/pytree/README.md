# SizeTree - Disk Space Analyzer

A TreeSize-like disk space analyzer built with **Textual** for interactive TUI and **Typer** for powerful CLI support.

## Features

- 🌳 **Interactive TUI** - Beautiful terminal UI with expandable tree view
- 📊 **CLI Mode** - Quick scans with table or tree output
- 📈 **Size Analysis** - Recursive directory scanning with human-readable sizes
- 🎯 **Smart Sorting** - Automatically sorts by size (largest first)
- ⚡ **Depth Control** - Limit scan depth for faster results
- 🔒 **Permission Handling** - Gracefully handles access denied errors
- 👁️ **Hidden Files** - Toggle visibility of hidden files (TUI mode)
- 💾 **File reports** - Save scans as plain text, JSON, Markdown, or HTML (`-o` / `--output`)

## Installation

```bash
pip install -r requirements.txt
```

`pytree --help` only lists commands (`scan`, `tui`, `version`). Options such as **`-o` / `--output`** live on **`scan`** — use **`pytree scan --help`**.

## Usage

### Quick Start

The simplest way to use SizeTree - just provide a path:

```bash
# Scan current directory
python pytree.py

# Scan any directory
python pytree.py C:\Users
python pytree.py /var/log
python pytree.py ..

# Add options directly
python pytree.py . --depth 2 --limit 10
python pytree.py ~/Downloads --tree
```

### Interactive TUI Mode

Launch the interactive Textual UI:

```bash
python pytree.py tui
python pytree.py tui /path/to/scan
python pytree.py tui . --depth 3
```

**TUI Keybindings:**
- `q` - Quit
- `r` - Rescan directory
- `h` - Toggle hidden files
- Arrow keys / Mouse - Navigate tree

### CLI Mode (Explicit)

Use the `scan` command explicitly:

```bash
# Scan current directory
python pytree.py scan

# Scan specific path
python pytree.py scan C:\Users

# Limit depth and number of items
python pytree.py scan . --depth 2 --limit 10

# Show as tree view
python pytree.py scan . --tree
```

### Options

**Scan Command:**
- `path` - Directory to scan (default: current directory)
- `--depth, -d` - Maximum depth to scan (default: unlimited)
- `--limit, -l` - Number of items to show (default: 20)
- `--tree, -t` - Show as tree view instead of table
- `--output, -o` - Write the report to a file (UTF-8). When set, the table/tree is written to the file only; a short confirmation is still printed in the terminal.
- `--format` - Report format: `text`, `json`, `markdown`, or `html`. If omitted, the format is inferred from the output filename (see below).

**Output file formats (scan only)**

| Extension | Format | Notes |
|-----------|--------|--------|
| `.txt` or no extension | text | Summary plus table or ASCII tree (same layout as CLI) |
| `.json` | json | Full tree as JSON (`scanned_path`, `generated_at`, `root` with nested `children`) |
| `.md`, `.markdown` | markdown | Summary plus a Markdown table or fenced tree |
| `.html`, `.htm` | html | Self-contained **dark-themed** page: storage chart (donut + bar), **sortable** table, **expandable** folder tree |

If the filename does not suggest a format (e.g. `report.out`), pass `--format` explicitly.

**TUI Command:**
- `path` - Directory to scan (default: current directory)
- `--depth, -d` - Maximum depth to scan (default: unlimited)

## Examples

```bash
# Quick scan of current directory
python pytree.py

# Scan Downloads folder with limit
python pytree.py ~/Downloads --limit 10

# Scan parent directory, 2 levels deep
python pytree.py .. --depth 2

# Deep analysis with TUI
python pytree.py tui /var/log

# Show tree view in CLI
python pytree.py . --tree --depth 2

# Scan Windows directory (explicit command)
python pytree.py scan C:\Windows --depth 1 --limit 5

# Save report: table as text, tree as Markdown, full data as JSON
python pytree.py scan ~/Projects -o report.txt
python pytree.py scan ~/Projects --tree -o tree.md
python pytree.py scan ~/Projects -o data.json --format json

# Show version
python pytree.py version
```

## Output Format

### Saved reports (`scan -o`)

Use `-o` with `--tree` for a tree-shaped report, or without `--tree` for the largest-items table. The table and tree list **both files and subfolders** in the scanned folder (sorted by size). JSON always includes the full scanned tree structure regardless of `-t` / `-l`.

HTML reports use a **dark theme** by default and include an interactive **storage overview** (share of total), a **sortable** “largest items” table (click column headers), and a **nested directory tree** with expand/collapse (`<details>` plus Expand all / Collapse all).

### Table View (CLI)
```
┌───┬──────────────┬──────────┬───────┬──────┬────────┐
│ # │ Name         │ Size     │ Files │ Dirs │ Type   │
├───┼──────────────┼──────────┼───────┼──────┼────────┤
│ 1 │ node_modules │ 2.3 GB   │ 45231 │ 8920 │ 📁 Dir │
│ 2 │ dist         │ 850.5 MB │ 892   │ 23   │ 📁 Dir │
└───┴──────────────┴──────────┴───────┴──────┴────────┘
```

### Tree View (CLI)
```
📁 project (3.2 GB)
├── 📁 node_modules (2.3 GB)
│   ├── 📁 package1 (150.0 MB)
│   └── 📁 package2 (120.0 MB)
└── 📁 dist (850.5 MB)
```

### Interactive TUI
```
┌─ SizeTree ────────────────────────────────────────────┐
│ Scanning: /home/user/projects                         │
│ Total Size: 5.2 GB                                    │
│ Files: 123,456 | Directories: 8,234                   │
├───────────────────────────────────────────────────────┤
│ 📁 project (3.2 GB)                                   │
│   📁 node_modules (2.3 GB)                            │
│   📁 dist (850.5 MB)                                  │
│   📁 src (45.2 MB)                                    │
└───────────────────────────────────────────────────────┘
 q Quit | r Rescan | h Toggle Hidden
```

## Requirements

- Python 3.8+
- Textual - Terminal UI framework
- Typer - CLI framework
- Rich - Terminal formatting

## Performance Tips

1. Use `--depth` to limit recursion depth for large directories
2. The TUI mode limits display to top 20 items per level for performance
3. Hidden files are skipped by default (toggle with `h` in TUI)
4. Permission errors are silently skipped

## License

Feel free to use and modify as needed!
