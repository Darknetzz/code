# Go

Small CLI utilities and network tools, each in its own module.

| Subdirectory | Description |
|-------------|-------------|
| [b64](b64/) | Base64 encode/decode from stdin or files. Supports standard, URL-safe, and ra... See [b64/README.md](b64/README.md) for details. |
| [gitt](gitt/) | Recursive Git helper CLI built as a standalone binary. See [gitt/README.md](gitt/README.md) for details. |
| [gofile](gofile/) | CLI to inspect and manage files — stat, hash, MIME type, size, list, cat, hea... See [gofile/README.md](gofile/README.md) for details. |
| [gohw](gohw/) | A command-line tool that displays hardware information about your computer wi... See [gohw/README.md](gohw/README.md) for details. |
| [gomatrix](gomatrix/) | — |
| [gonet](gonet/) | Network CLI tools — DNS, whois, port check, ping, HTTP headers/download, stat... See [gonet/README.md](gonet/README.md) for details. |
| [gotools](gotools/) | General-purpose CLI combining base64, checksums, and UUID generation. Run wit... See [gotools/README.md](gotools/README.md) for details. |
| [hashsum](hashsum/) | File checksum (hash) utility — compute or verify MD5, SHA1, SHA256, or SHA512... See [hashsum/README.md](hashsum/README.md) for details. |
| [refreshenv](refreshenv/) | Windows CLI that reloads User and Machine environment variables from the regi... See [refreshenv/README.md](refreshenv/README.md) for details. |
|-------------|-------------|

Each project has its own `go.mod`. Build from the project directory, e.g. `go build -o b64 .` in `b64/`.


Each project has its own `go.mod`. Build from the project directory, e.g. `go build -o b64 .` in `b64/`.
