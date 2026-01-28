# gotools

General-purpose CLI combining base64, checksums, and UUID generation. Run with no arguments to list commands; use `gotools help <command>` for per-command help.

## Build

```bash
go build -o gotools .
```

## Usage

```
gotools <command> [options] [args]
```

## Commands

### b64

Base64 encode/decode (stdin or file). Same behavior as the standalone [b64](../b64/) tool.

| Option | Description |
|--------|-------------|
| `-d`   | Decode instead of encode |
| `-i`   | Input file |
| `-o`   | Output file |
| `-raw` | Raw encoding (no padding) |
| `-url` | URL-safe encoding |

```bash
gotools b64 -d -i encoded.txt
echo "data" | gotools b64
```

### hash

Print or verify file checksums. With no files, hashes stdin. Algorithms: md5, sha1, sha256, sha512 (default: sha256).

| Option | Description |
|--------|-------------|
| `-a algo` | Algorithm: md5, sha1, sha256, sha512 |
| `-c file` | Verify checksums from file (one `hash  path` per line; lines starting with `#` or empty are ignored) |
| `-q`      | Quiet: print only the hash |

```bash
gotools hash file.zip
gotools hash -a md5 file1 file2
gotools hash -c checksums.sha256
echo "hello" | gotools hash -q
```

### uuid

Generate random UUIDs (v4). Optional argument is the count (default 1).

```bash
gotools uuid
gotools uuid 5
```
