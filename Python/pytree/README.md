# SizeTree - Disk Space Analyzer

A TreeSize-like disk space analyzer built with **Textual** for interactive TUI and **Typer** for powerful CLI support.

## Features

- 🌳 **Interactive TUI** - Beautiful terminal UI with expandable tree view
- 📊 **CLI Mode** - Quick scans with table or tree output
- 🌐 **HTML Reports** - Interactive, self-contained HTML reports that auto-open in your browser
- 📈 **Size Analysis** - Recursive directory scanning with human-readable sizes
- 🎯 **Smart Sorting** - Automatically sorts by size (largest first)
- ⚡ **Depth Control** - Limit scan depth for faster results
- 🔒 **Permission Handling** - Gracefully handles access denied errors
- 👁️ **Hidden Files** - Toggle visibility of hidden files (TUI mode)
- 💾 **File reports** - Save reports as HTML, plain text, JSON, or Markdown

## Installation

```bash
pip install -r requirements.txt
```

`pytree --help` lists the top-level commands: **`scan`** (terminal view), **`report`** (HTML/JSON/Markdown/text file, opens HTML in browser by default), **`tui`** (interactive explorer), and **`version`**. Use e.g. `pytree report --help` to see each command's options.

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

Use the `scan` command explicitly for a quick terminal view:

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

### Report Mode

Use the `report` command to generate a report file. By default it writes an interactive HTML report to a temp file and opens it in your default browser:

```bash
# Default: HTML report of current directory, opens in browser
python pytree.py report

# Save the report to a specific path
python pytree.py report ~/Projects -o report.html
python pytree.py report ~/Projects -o data.json
python pytree.py report ~/Projects -o tree.md --tree

# Pick a format without choosing a path (temp file is used)
python pytree.py report . --format markdown

# Generate HTML without opening a browser (good for CI/scripts)
python pytree.py report . --no-open
```

### Options

**Scan Command (terminal view):**
- `path` - Directory to scan (default: current directory)
- `--depth, -d` - Maximum depth to scan (default: unlimited)
- `--limit, -l` - Number of items to show (default: 20)
- `--tree, -t` - Show as tree view instead of table

**Report Command (file output):**
- `path` - Directory to scan (default: current directory)
- `--depth, -d` - Maximum depth to scan (default: unlimited)
- `--limit, -l` - Number of items to show (default: 20)
- `--tree, -t` - Render the report in tree form
- `--output, -o` - Write the report to this file (default: a temp file). UTF-8.
- `--format` - Report format: `text`, `json`, `markdown`, or `html`. Default: `html`. If `-o` is set without `--format`, the format is inferred from the filename extension.
- `--no-open` - Do not launch the browser for HTML reports

**Report file formats**

| Extension | Format | Notes |
|-----------|--------|--------|
| `.txt` or no extension | text | Summary plus table or ASCII tree (same layout as CLI) |
| `.json` | json | Full tree as JSON (`scanned_path`, `generated_at`, `root` with nested `children`) |
| `.md`, `.markdown` | markdown | Summary plus a Markdown table or fenced tree |
| `.html`, `.htm` | html | Self-contained **dark-themed** page: storage chart + one **merged** sortable / expandable table |

If the filename does not suggest a format (e.g. `report.out`), pass `--format` explicitly.

**TUI Command:**
- `path` - Directory to scan (default: current directory)
- `--depth, -d` - Maximum depth to scan (default: unlimited)

## Examples

```bash
# Quick terminal scan of current directory
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

# Generate and open an interactive HTML report of a project
python pytree.py report ~/Projects

# Save report: table as text, tree as Markdown, full data as JSON
python pytree.py report ~/Projects -o report.txt
python pytree.py report ~/Projects --tree -o tree.md
python pytree.py report ~/Projects -o data.json --format json

# Show version
python pytree.py version
```

## Output Format

### Saved reports (`report`)

Use `--tree` for a tree-shaped report, or omit it for the largest-items table. The table and tree list **both files and subfolders** in the scanned folder (sorted by size). JSON always includes the full scanned tree structure regardless of `-t` / `-l`.

HTML reports use a **dark theme** by default: an **interactive storage overview** (donut + stacked bar + legend) with checkboxes to **include or exclude** items (chart redraws to match), **hover tooltips** (name, type, size, bytes, file/dir counts, % of scan and of visible chart), and **click** on a segment or bar slice to toggle it like the checkbox. Below that, a **single “Contents” table** combines **sortable** top-level rows with **expandable** nested folder rows (nested **Share** is relative to that folder). Use **Expand all folders** / **Collapse all** for nested sections.

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
