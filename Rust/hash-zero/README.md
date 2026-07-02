# hash-zero

CLI for finding and verifying cryptographic hashes with leading or trailing runs of a hex character.

Brute-forces a nonce appended to a prefix (`find`) or checks a fixed input (`verify`). Supports SHA-256 and SHA-512. Match any hex digit with `--char`, or use `--unit bits` for zero-bit runs.

## Build

```powershell
cd Rust/hash-zero
cargo build --release
```

Release builds are recommended; the hot path is parallel hashing.

## Usage

```powershell
cargo run --release -- find "hello" --zeros 4 --unit hex
cargo run --release -- find "block" --zeros 3 --char f --side trailing
cargo run --release -- find "block" --zeros 16 --unit bits --side trailing
cargo run --release -- verify "hello45231" --zeros 4 --unit hex --json
```

### Subcommands

| Subcommand | Description |
|------------|-------------|
| `find <PREFIX>` | Brute-force `hash(prefix + nonce)` until the match target is met. |
| `verify <INPUT>` | Hash a fixed input and report whether it meets the target. |

### Shared flags

| Flag | Default | Description |
|------|---------|-------------|
| `--zeros <N>` | required | Target length of consecutive matching characters. |
| `--side leading\|trailing` | `leading` | Which end of the digest to match from. |
| `--char <DIGIT>` | `0` | Hex digit to match, or `any` for any repeated digit. |
| `--unit hex\|bits` | `hex` | Hex = consecutive matching nibbles; bits = consecutive zero bits. |
| `--algorithm sha256\|sha512` | `sha256` | Hash algorithm. |
| `--json` | off | Emit a JSON report. |

With `--unit bits`, only zero bits are supported (`--char` must be `0`; `any` is not allowed).

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

Each additional matching hex character multiplies expected search time by roughly 16×. Each additional zero bit multiplies it by roughly 2×.

### Examples

```powershell
# Find 4 leading hex zeroes (default --char 0)
.\target\release\hash-zero.exe find "hello" --zeros 4 --unit hex

# Find 3 trailing 'f' nibbles
.\target\release\hash-zero.exe find "test" --zeros 3 --char f --side trailing

# Find 3 leading repeats of any hex digit (e.g. aaa, fff, 000)
.\target\release\hash-zero.exe find "test" --zeros 3 --char any --side leading

# Find 16 trailing zero bits
.\target\release\hash-zero.exe find "block" --zeros 16 --unit bits --side trailing

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
progress: attempts=65.5K elapsed=2.0s rate=32.8K/s best=2/4 any nonce=65535
```

Final result on stdout:

```
nonce: 45231
input: hello45231
hash: aaa0a3f2c1...
run: 3 x 'a' (any, leading, hex)
attempts: 45.2K
elapsed_ms: 87
hash_rate: 520K/s
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (`find` found a match; `verify` meets target). |
| `1` | Failure (`verify` does not meet target, or invalid input / runtime error). |
