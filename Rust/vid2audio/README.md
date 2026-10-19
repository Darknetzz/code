# vid2audio

Cross-platform CLI that extracts audio from one or more video files using system ffmpeg. Defaults to Opus; override with `--format`.

## Requirements

- [FFmpeg](https://ffmpeg.org/) installed and on `PATH` (or set `FFMPEG_PATH` / pass `--ffmpeg`)
- Rust toolchain (to build)

## Build

```powershell
cd Rust/vid2audio
cargo build --release
```

Binary: `target/release/vid2audio` (or `vid2audio.exe` on Windows).

## Usage

```powershell
# Single file -> clip.opus next to the video
vid2audio clip.mp4

# Multiple files, MP3, custom output directory
vid2audio a.mkv b.webm --format mp3 -o .\audio

# Preview commands
vid2audio clip.mp4 --dry-run

# Overwrite existing outputs
vid2audio clip.mp4 --force
```

### Options

| Flag | Description |
|------|-------------|
| `INPUT...` | One or more video paths |
| `--format` | `opus` (default), `mp3`, `aac` (`.m4a`), `flac` |
| `-o`, `--output-dir` | Output directory (default: same as each input) |
| `--bitrate` | Bitrate in kbps (defaults: opus 128, mp3/aac 192; ignored for flac) |
| `--ffmpeg` | Path to ffmpeg binary |
| `--force` | Overwrite existing output files |
| `--dry-run` | Print ffmpeg commands without running |

Environment: `FFMPEG_PATH` overrides PATH when `--ffmpeg` is not set.

### Format mapping

| Format | Codec | Extension | Default bitrate |
|--------|-------|-----------|-----------------|
| opus | libopus | `.opus` | 128k |
| mp3 | libmp3lame | `.mp3` | 192k |
| aac | aac | `.m4a` | 192k |
| flac | flac | `.flac` | (lossless) |

## Notes

- Shell/PowerShell expands wildcards; pass multiple paths explicitly if needed.
- On convert failure the tool reports the error, continues with remaining inputs, and exits non-zero if any failed.
