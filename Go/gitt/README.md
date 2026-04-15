# gitt

Recursive Git helper CLI built as a standalone binary.

## Build

Local build:

```bash
go build -o gitt .
```

Versioned build (injects version metadata for `--version`):

```bash
go build -ldflags "-X gitt/internal/version.Version=v0.1.0 -X gitt/internal/version.Commit=$(git rev-parse --short HEAD) -X gitt/internal/version.BuildDate=$(date -u +%Y-%m-%dT%H:%M:%SZ)" -o gitt .
```

Or use `make release` (handles `date` on Unix and falls back on Windows).

## Usage

```text
gitt <command> [options]
```

Global flags (only as the first argument):

- `-h`, `--help`: Show help
- `-v`, `--version`: Show version

Most commands accept an optional **path** to scan (directory). If omitted, the **current working directory** is used.

Shared flags (where applicable):

- `--dry-run` (`pull` only): Print repositories that would be processed without pulling.
- `--max-depth <n>`: Limit recursion depth (`-1` means unlimited).
- `--jobs <n>`: Number of repositories to process in parallel (`list` does not use this).
- `--include-hidden`: Include hidden directories during discovery.
- `--verbose`: Print extra diagnostic output (stderr is serialized so lines do not interleave).

Interrupting with **Ctrl+C** (or SIGTERM on Unix) cancels in-flight `git` operations.

### pull

Recursively finds Git repositories from the scan root and runs `git pull --ff-only` for each clean repository.

Up-to-date vs updated is determined by comparing `HEAD` before and after the pull (not by parsing localized `git` messages).

```bash
gitt pull
gitt pull /path/to/projects
gitt pull --max-depth 3
```

`--max-depth -1` (default) scans the full directory tree. Use a non-negative value to limit how deep to walk from the scan root.

### list

Prints each discovered repository path (relative to the current working directory when possible), one per line.

```bash
gitt list
gitt list D:\src --max-depth 2
```

### fetch

Runs `git fetch --prune` in each discovered repository.

```bash
gitt fetch
gitt fetch ../worktrees --jobs 8
```

### status

Reports **clean** vs **dirty** using `git status --porcelain` (dirty repos show a short summary).

```bash
gitt status
gitt status . --include-hidden
```

## Install

Place the built binary (`gitt`/`gitt.exe`) in a directory that is on your `PATH`.
