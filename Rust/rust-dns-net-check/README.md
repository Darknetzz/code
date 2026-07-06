# rust-dns-net-check

**Canonical implementation.** Rust port of the legacy Python tool in `Python/dns-net-check/`. Prefer this build for release binaries (see `Rust/build.ps1`) and automation.

## Features

- DNS checks: `A`, `AAAA`, `CNAME`, `PTR`, `DNSSEC` (enabled by default)
- Network checks: TCP connect, HTTP probe, optional ping
- Human-readable table output and JSON output
- Deterministic exit codes for automation/CI

## Build

```powershell
cd Rust/rust-dns-net-check
cargo build --release
```

## Quick start

```powershell
cargo run --release -- --host example.com --port example.com:443 --url https://example.com --no-ping
cargo run --release
cargo run --release -- --config config.example.yaml
cargo run --release -- --config config.example.yaml --json
```

## CLI options

- `--config <path>`: YAML config file path
- `--host <hostname>`: host to test (repeatable)
- `--port <host:port>`: TCP target (repeatable)
- `--url <url>`: URL to probe (repeatable)
- `--timeout <seconds>`: default timeout (default: `5.0`)
- `--json`: emit JSON report
- `--no-ping`: disable ping checks
- `--dnssec`: force-enable DNSSEC checks for host targets
- `--no-dnssec`: disable DNSSEC checks for host targets
- `--nameserver <ip>`: custom DNS resolver

## Exit codes

- `0`: all checks passed
- `1`: one or more checks failed
- `2`: runtime/config/argument error

If you run with no targets and no config, the tool uses the same built-in baseline profile as the Python version.
