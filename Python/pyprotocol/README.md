# Lab Hop Protocol (LHP)

> **Canonical implementation:** [`Rust/rust-lhp`](../../Rust/rust-lhp/) (`rust-lhp` CLI) is the preferred server and client. This Python version remains for educational reference.

A secure, state-based network protocol implementation with replay protection and optional TLS encryption.

## Features

- **Replay Protection**: Uses timestamps to prevent replay attacks
- **Data Integrity**: XOR checksum validation
- **TLS Support**: Optional encryption for secure communication
- **Async/Await**: Built on Python's `asyncio` for high performance
- **State-Based Parsing**: Handles TCP fragmentation correctly

## Protocol Format

Each packet has the following structure:

```
+--------+----------+------+-----------+----------+-----------+
|  STX   |  Length  | CMD  | Timestamp | Payload  | Checksum  |
|  (1B)  |   (2B)   | (1B) |   (4B)    | (var)    |   (1B)    |
+--------+----------+------+-----------+----------+-----------+
```

- **STX**: Start byte (0x02)
- **Length**: Payload length (big-endian, 2 bytes)
- **CMD**: Command ID (0-255)
- **Timestamp**: Unix timestamp for replay protection (big-endian, 4 bytes)
- **Payload**: Variable-length command data
- **Checksum**: XOR checksum of payload (1 byte)

## Installation

No external dependencies required - uses only Python standard library:

```bash
# Python 3.7+ required
python --version
```

## Quick Start

### 1. Start the Server

**Without TLS (testing only):**
```bash
python server.py
```

**With TLS encryption:**
```bash
python server.py --tls --certfile server.crt --keyfile server.key
```

**Custom host/port:**
```bash
python server.py --host 127.0.0.1 --port 9999
```

### 2. Connect with Client

**Interactive mode** (send multiple commands):
```bash
python client.py localhost 8888 --interactive
```

**Single command:**
```bash
python client.py localhost 8888 --cmd 1 --data "Hello World"
```

**With TLS:**
```bash
python client.py localhost 8888 --tls --interactive
```

## Usage Examples

### Server Examples

```bash
# Basic server (no encryption)
python server.py

# Server on custom port
python server.py --port 9999

# Server with TLS
python server.py --tls --certfile server.crt --keyfile server.key --port 8888
```

### Client Examples

```bash
# Interactive mode
python client.py localhost 8888 -i

# Send single command
python client.py localhost 8888 --cmd 1 --data "reboot"
python client.py localhost 8888 --cmd 2 --data "Hello World"

# Client with TLS
python client.py localhost 8888 --tls --certfile server.crt --interactive
```

## Generating SSL Certificates

For testing with TLS, generate self-signed certificates:

**Using OpenSSL:**
```bash
openssl req -x509 -newkey rsa:4096 -nodes -keyout server.key -out server.crt -days 365 -subj "/CN=localhost"
```

**What this creates:**
- `server.key`: Private key file
- `server.crt`: Certificate file

## Project Structure

```
pyprotocol/
├── protocol.py    # Protocol implementation (LHPProtocol, LHPAsyncProtocol)
├── server.py      # Server implementation
├── client.py      # Client implementation
└── README.md      # This file
```

## Security Features

### Replay Protection

- Packets older than 5 minutes are rejected
- Duplicate timestamps (nonces) are detected and rejected
- Automatic cleanup of old nonces to prevent memory growth
- Allows 1 minute clock skew for network timing differences

### Data Integrity

- XOR checksum ensures payload integrity
- Corrupted packets are automatically dropped
- Clear error messages for debugging

### TLS Encryption

- Optional TLS encryption using Python's `ssl` module
- Supports self-signed certificates for testing
- Production-ready with proper certificate chain

## Protocol Implementation Details

### Packet Creation

```python
from protocol import LHPProtocol

# Create a packet
packet = LHPProtocol.create_packet(
    cmd_id=1,              # Command ID (0-255)
    data_bytes=b"Hello"    # Payload as bytes
)
```

### Server Implementation

The server uses `asyncio.Protocol` for efficient async I/O:

- Handles multiple concurrent connections
- Processes packets asynchronously
- Automatically handles TCP fragmentation
- State-based parsing ensures correct packet boundaries

### Client Implementation

The client supports two modes:

1. **Interactive Mode**: Connect and send multiple commands
2. **Single Command Mode**: Send one command and disconnect

## Error Handling

The protocol automatically handles:
- Malformed packets
- Replay attacks
- Corrupted data
- Connection timeouts
- Network errors

## Limitations

- **Timestamp Collisions**: If two packets have the exact same timestamp, the second is rejected. In practice, this is extremely rare.
- **Clock Skew**: Maximum 1 minute clock difference allowed between client and server.
- **Memory Growth**: Old nonces are cleaned up, but in high-frequency scenarios, consider additional cleanup strategies.

## Troubleshooting

### Connection Refused
```
✗ Connection refused - is the server running on localhost:8888?
```
**Solution**: Make sure the server is running and listening on the correct port.

### TLS Errors
```
SSL: CERTIFICATE_VERIFY_FAILED
```
**Solution**: Use `--certfile` option on the client, or disable verification for self-signed certs (already disabled by default).

### Replay Detection
```
Dropped packet: duplicate nonce detected (replay attack)
```
**Solution**: This is expected behavior when testing - wait a moment or use a different timestamp (automatic in normal use).

## License

This is an educational implementation for learning network protocols.

## Contributing

Feel free to improve the protocol, add features, or fix bugs!

## See Also

- Python `asyncio` documentation
- SSL/TLS best practices
- Network protocol design patterns
