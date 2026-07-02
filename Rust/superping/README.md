# Superping (Rust)

Feature-rich ICMP/TCP ping CLI — multi-host parallel probes, rich RTT statistics, continuous mode, DNS details, and JSON/YAML config.

## Features

- **Hybrid ICMP**: native Rust ICMP via `surge-ping`, with automatic fallback to system `ping` when raw sockets are blocked
- **Multi-host parallel** probing with comparison summary table
- **Rich statistics**: min/avg/max/stddev/jitter and packet loss
- **Continuous mode**: `--forever` with Ctrl+C summary
- **TCP probe mode** when ICMP is blocked (`--mode tcp --port 443`)
- **DNS context**: A/AAAA resolution, optional PTR (`--ptr`), IPv4/IPv6 filter
- Human-readable output and JSON for automation

## Build

```powershell
cd Rust/superping
cargo build --release
```

## Quick start

```powershell
cargo run --release -- 127.0.0.1 -c 3
cargo run --release -- --host 8.8.8.8 --host 1.1.1.1
cargo run --release -- --host 8.8.8.8 --host 1.1.1.1 --json
cargo run --release -- --mode tcp --port 443 --host example.com
cargo run --release -- --config config.example.yaml
cargo run --release -- --forever 127.0.0.1
```

## CLI options

- `--config <path>`: YAML config file
- `--host <hostname>`: target host (repeatable)
- `-c, --count <n>`: probes per host (default: 4)
- `--forever`: ping until interrupted
- `-i, --interval <secs>`: seconds between probes (default: 1.0)
- `--timeout <secs>`: per-probe timeout (default: 5.0)
- `--mode <icmp|tcp>`: probe mode (default: icmp)
- `--port <port>`: TCP port when mode is tcp (default: 443)
- `--ipv4` / `--ipv6`: address family filter
- `--ptr`: show reverse DNS for resolved IPs
- `--payload-size <n>`: ICMP payload bytes in native mode (default: 56)
- `--ttl <n>`: IP TTL in native ICMP mode
- `--subprocess`: force system ping instead of native ICMP
- `--json`: emit JSON report
- `-q, --quiet`: summary only (no per-reply lines)

Positional hosts are also accepted: `superping 8.8.8.8 example.com`.

## Windows note

Native ICMP may require elevation. When raw sockets are unavailable, superping automatically falls back to the system `ping` command.

## Exit codes

- `0`: all hosts had at least one successful reply (or TCP connect succeeded)
- `1`: one or more hosts fully unreachable / 100% packet loss
- `2`: config/argument/runtime error

## Network tests

Integration tests that hit the network are gated behind `SUPERPING_RUN_NET_TESTS=1`:

```powershell
$env:SUPERPING_RUN_NET_TESTS = "1"
cargo test
```
