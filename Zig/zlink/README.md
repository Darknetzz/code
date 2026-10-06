# zlink

Windows CLI for file/dir symlinks, junctions, and hard links.

Zig port of [`Python/pylink`](../../Python/pylink/), using native Win32 APIs (no `cmd mklink`).

## Requirements

- Windows only
- Zig 0.17+
- **Symlinks:** Administrator or [Developer Mode](https://learn.microsoft.com/en-us/windows/apps/get-started/enable-your-device-for-development)
- **Junctions:** Usually work without Developer Mode for directory targets on **local NTFS** (not network shares)

## Link types

| Type | Flag | When to use |
|------|------|-------------|
| File symlink | (default for files) | Point to a file |
| Directory symlink | `--dir` / `-d` | Symlink to a folder (needs symlink privilege). Default for **relative** targets and **network** paths |
| Junction | `--junction` / `-j` | Directory link on local NTFS; default for dirs with `--yes` and an **absolute** local target |
| Hard link | `--hard` / `-H` | Same-volume file alias (files only) |

Relative symlink targets are stored relative to the link's parent with POSIX separators, so Linux can follow the same string. Junctions always store an absolute NT path and cannot be created on a mapped/UNC share.

## Usage

```powershell
zlink C:\target D:\link
zlink C:\Projects\repo D:\repo-link -y
zlink fullcalendar-7.0.2 latest -y
zlink C:\assets\fullcalendar-7.0.2 C:\assets\latest --relative -d -y
zlink info D:\repo-link
zlink remove D:\repo-link -y
zlink C:\new\target D:\link --replace
```

## Build

```powershell
zig build
```

## Test

```powershell
zig build test
```
