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

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Quick Start

The simplest way to use SizeTree - just provide a path:

```bash
# Scan current directory
python sizetree.py

# Scan any directory
python sizetree.py C:\Users
python sizetree.py /var/log
python sizetree.py ..

# Add options directly
python sizetree.py . --depth 2 --limit 10
python sizetree.py ~/Downloads --tree
```

### Interactive TUI Mode

Launch the interactive Textual UI:

```bash
python sizetree.py tui
python sizetree.py tui /path/to/scan
python sizetree.py tui . --depth 3
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
python sizetree.py scan

# Scan specific path
python sizetree.py scan C:\Users

# Limit depth and number of items
python sizetree.py scan . --depth 2 --limit 10

# Show as tree view
python sizetree.py scan . --tree
```

### Options

**Scan Command:**
- `path` - Directory to scan (default: current directory)
- `--depth, -d` - Maximum depth to scan (default: unlimited)
- `--limit, -l` - Number of items to show (default: 20)
- `--tree, -t` - Show as tree view instead of table

**TUI Command:**
- `path` - Directory to scan (default: current directory)
- `--depth, -d` - Maximum depth to scan (default: unlimited)

## Examples

```bash
# Quick scan of current directory
python sizetree.py

# Scan Downloads folder with limit
python sizetree.py ~/Downloads --limit 10

# Scan parent directory, 2 levels deep
python sizetree.py .. --depth 2

# Deep analysis with TUI
python sizetree.py tui /var/log

# Show tree view in CLI
python sizetree.py . --tree --depth 2

# Scan Windows directory (explicit command)
python sizetree.py scan C:\Windows --depth 1 --limit 5

# Show version
python sizetree.py version
```

## Output Format

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
