# mediacut

Cross-platform CLI that cuts video/audio files with system ffmpeg: extract one or more time ranges, or remove ranges and join what remains.

## Requirements

- [FFmpeg](https://ffmpeg.org/) (and `ffprobe` for `--remove`) on `PATH`, or set `FFMPEG_PATH` / `FFPROBE_PATH` / pass `--ffmpeg` / `--ffprobe`
- Rust toolchain (to build)

## Build

```powershell
cd Rust/mediacut
cargo build --release
```

Binary: `target/release/mediacut` (or `mediacut.exe` on Windows).

## Usage

```powershell
# Single extract
mediacut in.mp4 --start 1:00 --end 2:00 -o clip.mp4

# Same with duration from start
mediacut in.mp4 --start 1:00 --duration 30 -o clip.mp4

# Multi-segment → separate files next to input
mediacut in.mp4 -s 0:10-0:20 -s 1:00-1:30

# Multi-segment → one joined file
mediacut in.mp4 -s 0:10-0:20 -s 1:00-1:30 --join -o highlights.mp4

# Remove ranges (keepers concatenated)
mediacut in.mp4 --remove 1:00-1:30 --remove 5:00-5:10 -o cleaned.mp4

# Frame-accurate re-encode (slower)
mediacut in.mp4 --start 1:00 --end 2:00 --reencode -o clip.mp4

# Preview commands
mediacut in.mp4 -s 0:10-0:20 --dry-run
```

Times: `SS`, `MM:SS`, or `HH:MM:SS` (fractional seconds OK, e.g. `1:02.5`).

### Options

| Flag | Description |
|------|-------------|
| `INPUT` | Input media path |
| `-s`, `--segment START-END` | Extract range (repeatable) |
| `--start TIME` | Extract start (with `--end` or `--duration`) |
| `--end TIME` | Extract end (with `--start`) |
| `--duration TIME` | Extract length from `--start` |
| `--remove START-END` | Drop range and keep the rest (repeatable; joined) |
| `--join` | Concatenate extracted segments into one file |
| `-o`, `--output PATH` | Output file (single/join/remove) or directory (multi-file) |
| `--reencode` | Re-encode for accurate cuts (default: stream copy) |
| `--ffmpeg` | Path to ffmpeg binary |
| `--ffprobe` | Path to ffprobe binary |
| `--force` | Overwrite existing outputs |
| `--dry-run` | Print ffmpeg commands without running |

Environment: `FFMPEG_PATH` / `FFPROBE_PATH` override PATH when the matching flag is not set.

## Notes

- Default is stream copy (`-c copy`): fast, but cuts snap to keyframes. Use `--reencode` when you need frame accuracy.
- `--remove` and `--segment` / `--start` cannot be mixed.
- `--join` only applies to extract mode; `--remove` always joins keepers into one file.
- Shell/PowerShell expands wildcards; pass the input path explicitly if needed.
