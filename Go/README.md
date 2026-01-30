# Go

Small CLI utilities and network tools, each in its own module.

| Subdirectory | Description |
|-------------|-------------|
| [b64](b64/) | Base64 encode/decode from stdin or files. Supports standard, URL-safe, and ra... See [b64/README.md](b64/README.md) for details. |
| [gofile](gofile/) | CLI to inspect and manage files — stat, hash, MIME, size, list, cat, head/tail, realpath, symlinks, copy, move, rm, mkdir, touch. See [gofile/README.md](gofile/README.md) for details. |
| [gonet](gonet/) | Network CLI tools — DNS, whois, port check, ping, HTTP headers/download, stat... See [gonet/README.md](gonet/README.md) for details. |
| [gotools](gotools/) | General-purpose CLI combining base64, checksums, and UUID generation. Run wit... See [gotools/README.md](gotools/README.md) for details. |
| [hashsum](hashsum/) | File checksum (hash) utility — compute or verify MD5, SHA1, SHA256, or SHA512... See [hashsum/README.md](hashsum/README.md) for details. |

Each project has its own `go.mod`. Build from the project directory, e.g. `go build -o b64 .` in `b64/`.
