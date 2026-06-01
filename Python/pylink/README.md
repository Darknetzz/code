# pylink

Windows CLI for creating file symlinks, directory symlinks, junctions, and hard links using native Win32 APIs (no `cmd mklink`).

## Requirements

- Windows only
- Python 3.9+
- `pip install -r requirements.txt` (Typer)
- **Symlinks:** Administrator or [Developer Mode](https://learn.microsoft.com/en-us/windows/apps/get-started/enable-your-device-for-development)
- **Junctions:** Usually work without Developer Mode for directory targets

## Link types

| Type | Flag | When to use |
|------|------|-------------|
| File symlink | (default for files) | Point to a file |
| Directory symlink | `--dir` / `-d` | Symlink to a folder (needs symlink privilege) |
| Junction | `--junction` / `-j` | Directory link; default for dirs with `--yes` |
| Hard link | `--hard` / `-H` | Same-volume file alias (files only) |

## Usage

```powershell
# Create link (default command — no subcommand name required)
pylink C:\target D:\link

# Junction with no prompts
pylink C:\Projects\repo D:\repo-link -y

# Inspect an existing link
pylink info D:\repo-link

# Remove a link only (not a real file/folder)
pylink remove D:\repo-link -y

# Replace existing link
pylink C:\new\target D:\link --replace
```

## Build

```powershell
# From repo root (requires pybin on PATH)
.\!scripts\build-python.ps1 -Projects pylink
```

## Tests

```powershell
cd Python
python -m pytest pylink/tests -q
```
