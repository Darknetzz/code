# GitHub Watcher v2.0

Monitor GitHub repositories for new releases and tags with automatic change detection.

## Overview

GitHub Watcher automatically tracks multiple GitHub repositories and notifies you when new releases or tags are detected. Built with **Typer** for a modern CLI interface and **Rich** for beautiful terminal output.

## Features

- ✅ **Check Releases** - Monitor repos for new releases and tags
- ✅ **Manage Repos** - Add, remove, and list tracked repositories  
- ✅ **Auto File Creation** - Automatically creates `repos.json` if missing with user confirmation
- ✅ **Change Detection** - Compares against cached versions for intelligent change tracking
- ✅ **Rich Formatting** - Beautiful colored tables and interactive prompts
- ✅ **Verbose Mode** - Get detailed output during checks

## Commands

```
check     Check all repos for new releases
list      List all repos in repos.json
add       Add a new repo
remove    Remove a repo
version   Show version
```

## Usage Examples

### List all tracked repos
```bash
github_watcher list
```

### Add a new repository
```bash
github_watcher add -u https://github.com/tiangolo/typer -n MyCustomName
```

### Check for new releases (with 2-second delay between requests)
```bash
github_watcher check --wait 2 --verbose
```

### Remove a repository
```bash
github_watcher remove -n MyCustomName
```

### Show version
```bash
github_watcher version
```

## Files

- `github_watcher.py` - Main application (v2.0 with Typer)
- `repos.json` - Stores tracked repositories (auto-created)
- `github_watcher.json` - Caches release/tag versions

## Requirements

- Python 3.7+
- Typer
- Rich
- requests
- BeautifulSoup4

## Installation

```bash
pip install typer rich requests beautifulsoup4
```

## Notes

- The script automatically creates `repos.json` if it doesn't exist (prompts user)
- Change detection compares current versions against cached versions
- Supports custom repo names or auto-generates from GitHub URL