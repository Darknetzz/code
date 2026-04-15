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

## Usage

```text
gitt <command> [options]
```

Global flags:

- `-h`, `--help`: Show help
- `-v`, `--version`: Show version

### pull

Recursively finds Git repositories from the current directory and runs `git pull --ff-only` for each clean repository.

```bash
gitt pull
```

Flags:

- `--dry-run`: Print repositories that would be processed without pulling.
- `--max-depth <n>`: Limit recursion depth (`-1` means unlimited).
- `--jobs <n>`: Number of repositories to process in parallel.
- `--include-hidden`: Include hidden directories during discovery.
- `--verbose`: Print extra diagnostic output.

## Install

Place the built binary (`gitt`/`gitt.exe`) in a directory that is on your `PATH`.
