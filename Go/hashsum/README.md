# hashsum

File checksum (hash) utility — compute or verify MD5, SHA1, SHA256, or SHA512. With no files, hashes stdin. Output format is compatible with `sha256sum`-style check files.

## Build

```bash
go build -o hashsum .
```

## Usage

```
hashsum [options] [file...]
```

## Options

| Flag | Description |
|------|-------------|
| `-a` | Hash algorithm: md5, sha1, sha256, sha512 (default: sha256) |
| `-q` | Quiet: print only the hash, no filename |
| `-c file` | Verify hashes from FILE — one line per `hash  path` (two spaces); blank lines and lines starting with `#` are skipped. Exit 1 if any mismatch. |

## Examples

```bash
# Default SHA256 of files
hashsum file.zip backup.tar

# MD5
hashsum -a md5 file.bin

# Hash stdin (e.g. pipe)
echo "hello" | hashsum -q

# Generate a checksum file
hashsum -a sha256 file1 file2 > checksums.sha256

# Verify from checksum file
hashsum -c checksums.sha256
```

Check file format: each line is `<hash><two spaces><path>`, e.g.:

```
d4735e3a265e16eee03f59718b9b5d03019c07d8b6c51f90da3a666eec13ab35  myfile.zip
```
