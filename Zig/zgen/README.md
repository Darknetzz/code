# zgen

Generate random strings of length N from presets or a custom charset.

## Usage

```powershell
zgen
zgen 48
zgen 32 -p base64
zgen 16 --charset 'ABCDEF#'
zgen 24 -p hex --count 5
zgen 64 --insecure
```

Default length is 32, preset is `alphanumeric`, and count is 1. Each string is printed on its own line. Randomness uses the OS entropy source unless `--insecure` is set.

## Options

| Flag | Meaning |
|------|---------|
| `[LENGTH]` | Output length (default: 32) |
| `-p`, `--preset NAME` | Character preset (default: `alphanumeric`) |
| `-c`, `--charset STR` | Custom charset (overrides `--preset`) |
| `-n`, `--count N` | Number of strings to print (default: 1) |
| `--insecure` | Use a fast non-crypto PRNG |
| `-h`, `--help` | Help |
| `-V`, `--version` | Version |

### Presets

| Name | Characters |
|------|------------|
| `alphanumeric` | `A-Za-z0-9` |
| `alphabetic` | `A-Za-z` |
| `lowercase` | `a-z` |
| `uppercase` | `A-Z` |
| `numeric` | `0-9` |
| `hex` | `0-9a-f` |
| `HEX` | `0-9A-F` |
| `base64` | `A-Za-z0-9+/` |
| `base64url` | `A-Za-z0-9-_` |

## Build

```powershell
zig build
zig build test
```
