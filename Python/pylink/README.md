# pylink

Windows CLI for creating file symlinks, directory symlinks, junctions, and hard links using native Win32 APIs (no `cmd mklink`).

## Requirements

- Windows only
- Python 3.9+
- `pip install -r requirements.txt` (Typer)
- **Symlinks:** Administrator or [Developer Mode](https://learn.microsoft.com/en-us/windows/apps/get-started/enable-your-device-for-development)
- **Junctions:** Usually work without Developer Mode for directory targets on **local NTFS** (not network shares)

## Link types

| Type | Flag | When to use |
|------|------|-------------|
| File symlink | (default for files) | Point to a file |
| Directory symlink | `--dir` / `-d` | Symlink to a folder (needs symlink privilege). Default for **relative** targets and **network** paths |
| Junction | `--junction` / `-j` | Directory link on local NTFS; default for dirs with `--yes` and an **absolute** local target |
| Hard link | `--hard` / `-H` | Same-volume file alias (files only) |

Relative symlink targets are stored relative to the link's parent with POSIX separators (`latest -> fullcalendar-7.0.2`), so Linux can follow the same string. Junctions always store an absolute NT path and cannot be created on a mapped/UNC share.

## Version pointer on a NAS

For `latest -> fullcalendar-7.0.2` on a share (`Z:` / `\\nas3\share`):

```powershell
pylink fullcalendar-7.0.2 latest -y
```

That stores a directory symlink with a relative target. Do **not** use `--junction`: junctions require local NTFS, and an absolute `Z:\...` target is a dead link on Linux.

`--relative` / `-R` (like `ln -sr`) rewrites an absolute target to a path relative to the link parent.

Creating the POSIX symlink **on the Linux/Samba side** is still the most compatible option: Windows then sees a normal directory (no reparse point, no per-machine R2R policy):

```bash
ln -s fullcalendar-7.0.2 latest
```

Windows will not follow a share-to-share symlink until `SymlinkEvaluation R2R` is enabled on that PC (`fsutil behavior set SymlinkEvaluation R2R:1`). That is machine-wide and can be overridden by Group Policy; pylink will warn but will not change it.

## Usage

```powershell
# Create link (default command — no subcommand name required)
pylink C:\target D:\link

# Junction with no prompts (local NTFS, absolute target)
pylink C:\Projects\repo D:\repo-link -y

# Relative directory symlink (NAS / Linux-portable)
pylink fullcalendar-7.0.2 latest -y

# Force a relative stored target from an absolute path
pylink C:\assets\fullcalendar-7.0.2 C:\assets\latest --relative -d -y

# Inspect an existing link (prints the raw stored target)
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
