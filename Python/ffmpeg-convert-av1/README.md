# convert_av1

A fast, reliable video batch converter that targets the best available encoder on your system (AV1 on NVIDIA/AMD GPUs when possible, otherwise HEVC or CPU AV1), with safe defaults to reduce file size by ~50% while preserving quality.

## Features

- Auto-detects best encoder: `av1_nvenc` → `av1_amf` → `hevc_nvenc` → `hevc_amf` → `libsvtav1`
- Smart bitrate selection: probes input bitrate and targets 50% reduction
- Preserves multi‑channel audio (uses Opus at 64 kbps per stream)
- Safe batch processing: disk space checks, temp file swap, overwrite prompts
- Skips files that already use the target codec
- Clean CLI with helpful messages (powered by Typer + Rich)

## Requirements

- FFmpeg and FFprobe installed and available on PATH
- Python 3.9+
- Python packages: `typer`, `rich`

### Install Python dependencies

```powershell
python -m pip install -r requirements.txt
```

If you prefer to install directly:

```powershell
python -m pip install typer rich
```

## Usage

Basic usage examples (Windows PowerShell):

```powershell
# Convert a single file in-place
python convert_av1.py "C:\Videos\movie.mkv"

# Convert a single file to a specific output folder
python convert_av1.py "C:\Videos\movie.mkv" "C:\Converted"

# Convert a folder (outputs to same folder unless you provide one)
python convert_av1.py "C:\Videos\Input"
python convert_av1.py "C:\Videos\Input" "C:\Videos\Output"

# Auto-delete originals after successful conversion
python convert_av1.py "C:\Videos\movie.mkv" --delete-original

# Force overwrite existing outputs
python convert_av1.py "C:\Videos\movie.mkv" --overwrite

# Manually set target video bitrate
python convert_av1.py "C:\Videos\movie.mkv" --bitrate 2500k
python convert_av1.py "C:\Videos\movie.mkv" --bitrate 2.5m
python convert_av1.py "C:\Videos\movie.mkv" --dry-run
```

## Command reference

```text
Usage: python convert_av1.py [INPUT_PATH] [OUTPUT_DIR] [OPTIONS]

Arguments:
  INPUT_PATH    Path to input (file or folder)
  OUTPUT_DIR    Optional output directory (defaults to input or same folder)

Options:
  --bitrate TEXT          Override video bitrate (e.g., 2500k, 2m)
  -d, --delete-original   Auto-delete originals after successful conversion
  -o, --overwrite         Overwrite existing output files
  -V, --version           Show version and exit
  --help                  Show this message and exit
  --dry-run               Print planned actions without converting
```

## How it works

1. Checks that `ffmpeg` is available.
2. Detects the best available encoder in this order:
   - NVIDIA AV1 (`av1_nvenc`) → AMD AV1 (`av1_amf`) → NVIDIA HEVC (`hevc_nvenc`) → AMD HEVC (`hevc_amf`) → CPU AV1 (`libsvtav1`).
3. For each video file:
   - Skips if already encoded with the target codec (AV1 or HEVC).
   - Probes input bitrate and sets target to ~50% (configurable).
   - Applies safe scaling (max width 1920) keeping aspect ratio.
   - Encodes video with VBR using sensible `-b:v`, `-maxrate`, and `-bufsize`.
   - Preserves audio channels and re-encodes to Opus 64k.
   - Writes to a temp `.temp.mkv`, then atomically swaps on success.
   - Optionally deletes or prompts to delete the original; can rename output to original name when converting in-place.

## Notes and defaults

- Pixel format: `nv12` for hardware encoders, `yuv420p` for CPU.
- Scaling: `min(1920, iw)` to cap at 1080p while preserving aspect ratio.
- HEVC outputs are tagged `hvc1` for broader compatibility.
- Output container: `.mkv` with `+faststart` for faster playback start.
- Supported input extensions: `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`.
- Disk space safety: requires ~1.5× the input file size free in the output drive.

## Tips

- For archival quality, you can raise the bitrate or use CPU AV1 with `--bitrate`.
- If you see larger outputs, the source may already be efficient (e.g., high-entropy or already AV1/HEVC). The script warns and lets you choose deletion.
- To batch large folders, start with `--overwrite` only when you’re confident in the settings.

## Troubleshooting

- "ffmpeg is not found" → Install FFmpeg and ensure `ffmpeg.exe` and `ffprobe.exe` are in PATH.
- "Insufficient disk space" → Free space or change `OUTPUT_DIR` to a drive with more room.
- Hardware encoder not detected → Update GPU drivers; verify FFmpeg build includes NVENC/AMF.

## License

This project is provided as-is without warranty. Use at your own risk.
