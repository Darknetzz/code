# zwhich

PATH lookup that lists every match and marks which entry wins.

## Usage

```powershell
zwhich git
zwhich -1 python
zwhich --no-cwd zig
```

Exit status is `0` when every name is found, `1` otherwise.

## Options

| Flag | Meaning |
|------|---------|
| `-1`, `--first` | Print only the winner (unix `which` style) |
| `--no-cwd` | Do not search the current directory first (Windows searches cwd by default) |
| `--cwd` | Search cwd first (default on Windows) |
| `--path PATH` | Use this `PATH` instead of the process environment |
| `--pathext EXTS` | Override `PATHEXT` (Windows; e.g. `.EXE;.CMD`) |
| `-h`, `--help` | Help |
| `-V`, `--version` | Version |

Windows applies `PATHEXT` in each directory, in list order, like `CreateProcess`. Duplicate PATH folders are collapsed.

## Build

```powershell
zig build
zig build test
```
