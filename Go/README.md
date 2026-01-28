# Go

Small CLI utilities and network tools, each in its own module.

| Subdirectory | Description |
|-------------|-------------|
| **b64** | Base64 encode/decode — stdin or files; optional URL-safe and raw encoding. |
| **gonet** | Network tools: DNS, whois, port check, ping, HTTP headers/download, static server, TLS cert info, URL encode, JWT decode. See [gonet/README.md](gonet/README.md) for details. |
| **gotools** | Multi-command CLI: `b64`, `hash` (md5/sha1/sha256/sha512), and `uuid`. |
| **hashsum** | File checksum utility — md5, sha1, sha256, sha512; can verify hashes from a file. |

Each project has its own `go.mod`. Build from the project directory, e.g. `go build -o b64 .` in `b64/`.
