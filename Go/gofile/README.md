# gofile

CLI to inspect and manage files — stat, hash, MIME type, size, list, cat, head/tail, realpath, symlink/readlink, copy, move, remove, mkdir, touch.

## Usage

```
gofile <command> [options] [args]
```

## Build

```bash
go build -o gofile .
```

## Commands

### Inspect

| Command   | Description |
|-----------|-------------|
| `info`    | File/dir metadata (path, size, mode, mtime); `-l` long format |
| `hash`    | Checksum (md5, sha256, sha512); `-a algo`, `-q` quiet. Stdin if no path. |
| `type`    | MIME type (from content + extension) |
| `size`    | Human-readable size; `-R` recursive for dirs |
| `list`    | List directory; `-l` long, `-R` recursive |
| `cat`     | Print file(s); stdin if no path |
| `head`    | First N lines (default 10) or `-c N` bytes |
| `tail`    | Last N lines (default 10) or `-c N` bytes |
| `realpath`| Resolve to absolute path (follows symlinks) |

### Symlinks

| Command   | Description |
|-----------|-------------|
| `symlink` | Create symbolic link: `symlink <target> <linkpath>` |
| `readlink`| Print symlink target(s); `-f` resolve to final realpath (one path) |

### Manage

| Command   | Description |
|-----------|-------------|
| `copy`    | Copy file(s) to destination; `-r` recursive for dirs |
| `move`    | Move file(s); cross-device = copy + remove |
| `remove`  | Delete file(s); `-r` recursive, `-f` ignore missing |
| `mkdir`   | Create directory; `-p` parents |
| `touch`   | Create empty file or update mtime |

Aliases: `stat`→info, `ls`→list, `link`→symlink, `cp`→copy, `mv`→move, `rm`→remove, `real`→realpath, `mime`→type.

## Examples

```bash
gofile info -l README.md
gofile hash -a sha256 -q gofile.go
gofile type image.png
gofile size -R .
gofile list -l
gofile cat config.json
gofile head -n 20 log.txt
gofile tail -c 1024 data.bin
gofile realpath ../other
gofile symlink /path/to/target mylink
gofile readlink mylink
gofile readlink -f mylink
gofile copy -r src/ backup/
gofile move old.txt new.txt
gofile remove -rf tmp/
gofile mkdir -p a/b/c
gofile touch newfile.txt
```
