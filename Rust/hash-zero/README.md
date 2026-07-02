# hash-zero

CLI for finding and verifying cryptographic hashes with leading or trailing zeroes.

Brute-forces a nonce appended to a prefix (`find`) or checks a fixed input (`verify`). Supports SHA-256 and SHA-512, with zeroes counted as hex nibbles or raw bits.

## Build

```powershell
cd Rust/hash-zero
cargo build --release
```

Release builds are recommended; the hot path is parallel hashing.

## Usage

```powershell
cargo run --release -- find "hello" --zeros 4 --unit hex
cargo run --release -- find "block" --zeros 16 --unit bits --trailing
cargo run --release -- verify "hello45231" --zeros 4 --unit hex --json
```

### Subcommands

| Subcommand | Description |
|------------|-------------|
| `find <PREFIX>` | Brute-force `hash(prefix + nonce)` until the zero target is met. |
| `verify <INPUT>` | Hash a fixed input and report whether it meets the target. |

### Shared flags

| Flag | Default | Description |
|------|---------|-------------|
| `--zeros <N>` | required | Target count of leading or trailing zeroes. |
| `--leading` | on | Count zeroes from the start of the digest. |
| `--trailing` | off | Count zeroes from the end of the digest. |
| `--unit hex\|bits` | `hex` | Hex = consecutive `0` nibbles; bits = consecutive zero bits. |
| `--algorithm sha256\|sha512` | `sha256` | Hash algorithm. |
| `--json` | off | Emit a JSON report. |

`--leading` and `--trailing` are mutually exclusive. When neither is given, leading is used.

### `find` flags

| Flag | Default | Description |
|------|---------|-------------|
| `--nonce-start <N>` | `0` | Starting nonce value. |
| `--nonce-format decimal\|hex` | `decimal` | How the nonce is appended to the prefix. |
| `--threads <N>` | all CPUs | Rayon worker thread count. |
| `--progress` | on (unless `--json`) | Show live search progress on stderr. |
| `--no-progress` | | Disable progress output. |
| `--progress-interval <MS>` | `1000` | How often to refresh progress (milliseconds). |

### Difficulty

Each additional hex zero multiplies expected search time by roughly 16×. Each additional bit multiplies it by roughly 2×.

### Examples

```powershell
# Find a SHA-256 hash with 4 leading hex zeroes
.\target\release\hash-zero.exe find "hello" --zeros 4 --unit hex

# Find 16 trailing zero bits with SHA-256
.\target\release\hash-zero.exe find "block" --zeros 16 --unit bits --trailing

# Verify an input (exit 0 if target met, 1 if not)
.\target\release\hash-zero.exe verify "hello12345" --zeros 2 --unit hex

# JSON output
.\target\release\hash-zero.exe find "test" --zeros 3 --unit hex --json

# Live progress on stderr (default for human output)
.\target\release\hash-zero.exe find "hello" --zeros 5 --unit hex --progress-interval 500
```

### Default `find` output

Progress updates are written to stderr while searching (disabled with `--json` or `--no-progress`):

```
progress: attempts=65536 elapsed=2.0s rate=32768/s best=2/4 nonce=65535
```

Final result on stdout:
nonce: 45231
input: hello45231
hash: 0000a3f2c1...
zeroes: 4 (leading, hex)
attempts: 45232
elapsed_ms: 87
hash_rate: 519885/s
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (`find` found a match; `verify` meets target). |
| `1` | Failure (`verify` does not meet target, or invalid input / runtime error). |
