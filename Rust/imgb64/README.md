# imgb64

CLI for encoding images to data URIs (or raw base64) and decoding either form back to image files. Complements the generic Go [`b64`](../../Go/b64/) tool with image-oriented MIME handling.

## Build

```powershell
cd Rust/imgb64
cargo build --release
```

## Usage

```powershell
# Encode to data URI (stdout)
imgb64 encode photo.png

# Encode to raw base64 only
imgb64 encode photo.png --raw

# Encode to a file
imgb64 encode photo.png -o photo.txt

# Decode data URI or raw base64 to an image
imgb64 decode photo.txt -o restored.png

# Stdin / stdout with `-`
Get-Content photo.png -AsByteStream | imgb64 encode - --raw
imgb64 decode encoded.txt -o -
```

### Commands

| Command | Description |
|---------|-------------|
| `encode <INPUT>` | Read image bytes; write `data:<mime>;base64,...` (default) or raw base64 with `--raw` |
| `decode <INPUT>` | Read a data URI or raw base64; write image bytes |

### Options

| Flag | Description |
|------|-------------|
| `-o`, `--output` | Output path (`-` for stdout; default stdout) |
| `--raw` | (`encode` only) Emit base64 payload without a `data:` prefix |

MIME is taken from the file extension when possible, otherwise sniffed from magic bytes (PNG/JPEG/GIF/WebP/BMP). On decode, if `-o` has no extension and the input was a data URI, a matching extension is appended.
