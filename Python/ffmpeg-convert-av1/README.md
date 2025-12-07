# av1

A fast, reliable video batch converter that targets the best available encoder on your system (AV1 on NVIDIA/AMD GPUs when possible, otherwise HEVC or CPU AV1), with safe defaults to reduce file size by ~50% while preserving quality.

## Features

- Auto-detects best encoder: `av1_nvenc` → `av1_amf` → `hevc_nvenc` → `hevc_amf` → `libsvtav1`
- Smart bitrate selection: probes input bitrate and targets 50% reduction
- Preserves multi‑channel audio (uses Opus at 64 kbps per stream)
- Safe batch processing: disk space checks, temp file swap, overwrite prompts
- Skips files that already use the target codec
- **Wildcard pattern support**: Convert files matching patterns like `test*.mp4` or `video_?.mkv`
- **Progress tracking**: Real-time progress with elapsed time, ETA, and live savings counter
- **Graceful cancellation**: Press Ctrl+C to stop after current file and save progress summary
- **Automatic logging**: Save all output to `.txt` or `.html` logs (configurable)
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
av1 "C:\Videos\movie.mkv"

# Convert a single file to a specific output folder
av1 "C:\Videos\movie.mkv" "C:\Converted"

# Convert all files matching a wildcard pattern
av1 "test*.mp4"
av1 "C:\Videos\vacation_*.mkv" "C:\Converted"

# Convert a folder (outputs to same folder unless you provide one)
av1 "C:\Videos\Input"
av1 "C:\Videos\Input" "C:\Videos\Output"

# Auto-delete originals after successful conversion
av1 "C:\Videos\movie.mkv" --delete-original

# Force overwrite existing outputs
av1 "C:\Videos\movie.mkv" --overwrite

# Manually set target video bitrate
av1 "C:\Videos\movie.mkv" --bitrate 2500k
av1 "C:\Videos\movie.mkv" --bitrate 2.5m

# Dry run: show what would happen without converting
av1 "C:\Videos\movie.mkv" --dry-run

# Process folder recursively (includes all subdirectories)
av1 "C:\Videos\Input" --recursive
av1 "C:\Videos\Input" -r

# Save logs (default: ./logs/ as .txt)
av1 "C:\Videos\Input" --log-type txt
av1 "C:\Videos\Input" --log-type html
av1 "C:\Videos\Input" --log-type none  # Disable logging

# Custom log directory
av1 "C:\Videos\Input" --log-dir "C:\MyLogs" --log-type html

# Keep .mkv extension when converting in-place
av1 "C:\Videos\movie.mp4" --delete-original --keep-mkv
```

## Command reference

```text
Usage: av1 [INPUT_PATH] [OUTPUT_DIR] [OPTIONS]

Arguments:
  INPUT_PATH    Path to input (file or folder) - supports wildcards like 'test*.mp4'
  OUTPUT_DIR    Optional output directory (defaults to input or same folder)

Options:
  --bitrate TEXT          Override video bitrate (e.g., 2500k, 2m)
  -d, --delete-original   Auto-delete originals after successful conversion
  -o, --overwrite         Overwrite existing output files
  --dry-run               Print planned actions without converting
  -r, --recursive         Process subdirectories recursively
  --keep-mkv              Keep .mkv extension instead of matching original filename
  --log-type TEXT         Log output type: 'txt' (default), 'html', or 'none' to disable
  --log-dir TEXT          Directory to save logs (default: ./logs)
  -V, --version           Show version and exit
  --help                  Show this message and exit
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

- **Use wildcards** to batch process files matching a pattern: `av1 "episode_*.mkv"`
- **Progress tracking** shows real-time file counter, elapsed time, ETA, and cumulative space saved.
- **Graceful stopping**: Press `Ctrl+C` once to finish the current file and display a summary. Press `Ctrl+C` again to force quit immediately.
- **Logging** automatically saves all output to timestamped files in `./logs/`. Use `--log-type html` for styled HTML logs or `--log-type none` to disable.
- Use `--recursive` to process entire folder trees with subdirectories, preserving structure when using a separate output folder.
- For archival quality, you can raise the bitrate or use CPU AV1 with `--bitrate`.
- If you see larger outputs, the source may already be efficient (e.g., high-entropy or already AV1/HEVC). The script warns and lets you choose deletion.
- To batch large folders, start with `--overwrite` only when you're confident in the settings.
- Combine `--dry-run` with `--recursive` to preview all files that would be processed before committing to conversion.
- Use `--keep-mkv` to preserve the `.mkv` extension when converting files in-place (useful for maintaining consistent naming).

## Troubleshooting

- "ffmpeg is not found" → Install FFmpeg and ensure `ffmpeg.exe` and `ffprobe.exe` are in PATH.
- "Insufficient disk space" → Free space or change `OUTPUT_DIR` to a drive with more room.
- Hardware encoder not detected → Update GPU drivers; verify FFmpeg build includes NVENC/AMF.

## Shell Completion

To enable tab completion in PowerShell:

1. Create the completions directory:
   ```bash
   mkdir ~\Documents\PowerShell\completions
   ```

2. Generate the completion script:
   ```bash
   av1 --show-completion > ~\Documents\PowerShell\completions\av1-completion.ps1
   ```

3. Add to your PowerShell profile (`$PROFILE`):
   ```powershell
   # Load all completion scripts
   Get-ChildItem "$HOME\Documents\PowerShell\completions\*.ps1" | ForEach-Object { . $_ }
   ```

4. Reload your profile:
   ```powershell
   . $PROFILE
   ```

5. After modifying CLI options, regenerate the completion:
   ```bash
   av1 --show-completion > ~\Documents\PowerShell\completions\av1-completion.ps1
   ```

**Note:** Avoid using `--install-completion` as it appends directly to your profile without formatting and can create duplicates. Use `--show-completion` and manually manage completion scripts instead.

## License

This project is provided as-is without warranty. Use at your own risk.
