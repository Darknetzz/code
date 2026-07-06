# lhp (Lab Hop Protocol)

Rust port of the Python network protocol in `Python/pyprotocol/`.

Secure, state-based TCP protocol with replay protection (timestamps), XOR checksum validation, and optional TLS.

## Build

```powershell
cd Rust/lhp
cargo build --release
```

## Usage

```powershell
# Server (plaintext, testing only)
cargo run --release -- server --port 8888

# Server with TLS
cargo run --release -- server --tls --certfile server.crt --keyfile server.key

# Client single command
cargo run --release -- client localhost 8888 --cmd 1 --data "Hello World"

# Interactive client
cargo run --release -- client localhost 8888 -i
```

## Protocol format

| Field | Size |
|-------|------|
| STX | 1 byte (0x02) |
| Length | 2 bytes BE |
| CMD | 1 byte |
| Timestamp | 4 bytes BE |
| Payload | variable |
| Checksum | 1 byte (XOR of payload) |

> **Legacy / reference:** The Python implementation in `Python/pyprotocol/` remains for educational comparison.
