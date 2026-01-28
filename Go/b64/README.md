# b64

Base64 encode/decode from stdin or files. Supports standard, URL-safe, and raw (unpadded) encodings.

## Build

```bash
go build -o b64 .
```

## Usage

```
b64 [options] [file]
```

With no file and no `-i`, reads from stdin. Default is encode; use `-d` to decode.

## Options

| Flag   | Description |
|--------|-------------|
| `-d`   | Decode instead of encode |
| `-i`   | Input file (default: stdin) |
| `-o`   | Output file (default: stdout) |
| `-raw` | Raw encoding — no padding |
| `-url` | URL-safe encoding (e.g. JWTs, query params) |

## Examples

```bash
# Encode stdin
echo "hello" | b64

# Decode stdin
echo "aGVsbG8=" | b64 -d

# File in/out
b64 -i in.bin -o out.txt
b64 -d -i out.txt -o restored.bin

# Positional file (input only)
b64 secret.bin
b64 -d -i encoded.txt

# URL-safe (e.g. JWTs)
b64 -url -d -i token.txt
```
