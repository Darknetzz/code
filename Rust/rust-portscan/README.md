# rust-portscan

Rust port of the Python TCP port scanner in `Python/pyportscanner/`.

Scans one or more IPv4 addresses for open TCP ports with concurrent async connections.

## Build

```powershell
cd Rust/rust-portscan
cargo build --release
```

## Usage

```powershell
cargo run --release -- 127.0.0.1
cargo run --release -- 192.168.1.1 192.168.1.2 -p 80,443,8080
cargo run --release -- 192.168.1.1 -p 1-1000 -t 2 -w 200
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `-p, --ports` | common ports | Port list or ranges (`80`, `1-100`, `1-100,443`) |
| `-t, --timeout` | `1.0` | Connect timeout in seconds |
| `-w, --workers` | `100` | Max concurrent connections |

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Scan completed |
| `2` | Invalid arguments or runtime error |
