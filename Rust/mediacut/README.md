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

Binaries: `target/release/mediacut` and `target/release/mediawave` (`.exe` on Windows).

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

---

# mediawave

Companion binary (same crate) that shows a waveform for audio or video (first audio stream): terminal blocks by default, optional PNG via ffmpeg `showwavespic`.

## Usage

```powershell
# Terminal peaks (default)
mediawave track.mp3
mediawave clip.mp4 --width 100 --height 16

# PNG image
mediawave track.mp3 -o wave.png
mediawave track.mp3 -o wave.png --width 1280 --height 240

# Both terminal and PNG
mediawave track.mp3 -o wave.png --terminal

# Time window
mediawave track.mp3 --start 1:00 --duration 30 -o clip-wave.png

# Preview ffmpeg commands
mediawave track.mp3 -o wave.png --dry-run
```

### Options

| Flag | Description |
|------|-------------|
| `INPUT` | Audio or video path |
| `-o`, `--output PATH` | Write PNG (default: terminal only) |
| `--terminal` | Also print terminal waveform when writing PNG |
| `--width N` | Columns (terminal, default 80) or pixels (PNG, default 1280) |
| `--height N` | Rows (terminal, default 12) or pixels (PNG, default 240) |
| `--start` / `--end` / `--duration` | Optional time window |
| `--ffmpeg` | Path to ffmpeg binary |
| `--force` | Overwrite existing PNG |
| `--dry-run` | Print ffmpeg commands without running |

Defaults: no `-o` → terminal only; `-o` set → PNG only unless `--terminal`. PNG uses a dark background and cyan mono trace (`scale=sqrt`).
