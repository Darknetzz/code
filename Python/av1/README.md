# av1

A fast, reliable video batch converter that targets the best available encoder on your system (AV1 on NVIDIA/AMD GPUs when possible, otherwise HEVC or CPU AV1), with safe defaults to reduce file size by ~50% while preserving quality.

## Features

- **Auto-detects best encoder**: `av1_nvenc` → `av1_amf` → `hevc_nvenc` → `hevc_amf` → `libsvtav1`
- **Smart bitrate selection**: Probes input bitrate and targets ~50% reduction (configurable)
- **Preserves audio**: Multi-channel audio using Opus codec (configurable bitrate)
- **Safe batch processing**: Disk space checks, temp file swap, overwrite prompts, graceful Ctrl+C handling
- **Skips re-encoding**: Skips files that already use the target codec
- **Wildcard patterns**: Convert files matching patterns like `test*.mp4` or `video_?.mkv`
- **Rich progress tracking**: Nested progress bars with per-file FPS, ETA, and cumulative savings
- **Multiple log formats**: `.txt`, `.html`, or `.json` (structured for automation)
- **Flexible ffmpeg/ffprobe**: Override paths via CLI or environment variables with automatic PATH fallback
- **Environment-driven**: Configure defaults via env vars for headless/automation use
- **Non-interactive mode**: `--no-prompt` for automation scripts, CI/CD pipelines
- **Dry-run support**: Preview changes without converting

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

# Suppress interactive prompts (useful for scripts/automation)
av1 "C:\Videos\movie.mkv" --no-prompt

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

# Save logs in different formats
av1 "C:\Videos\Input" --log-type txt      # Default: plain text
av1 "C:\Videos\Input" --log-type html     # Styled HTML
av1 "C:\Videos\Input" --log-type json     # Structured JSON for automation
av1 "C:\Videos\Input" --log-type none     # Disable logging

# Custom log directory
av1 "C:\Videos\Input" --log-dir "C:\MyLogs" --log-type json

# Keep .mkv extension when converting in-place
av1 "C:\Videos\movie.mp4" --delete-original --keep-mkv

# Override ffmpeg/ffprobe paths
av1 "C:\Videos\Input" --ffmpeg "C:\custom\ffmpeg.exe" --ffprobe "C:\custom\ffprobe.exe"

# Disable colored output (useful for piping or logs)
av1 "C:\Videos\Input" --no-color
```

## Command reference

```text
Usage: av1 [INPUT_PATHS]... [OPTIONS]

Arguments:
  INPUT_PATHS     Paths to input (file or folder) - supports wildcards like 'test*.mp4'

Options:
  --output-dir TEXT           Output directory (defaults to input folder)
  --bitrate TEXT              Override video bitrate (e.g., 2500k, 2m)
  -d, --delete-original       Auto-delete originals after successful conversion
  -o, --overwrite             Overwrite existing output files
  --dry-run                   Show planned actions without converting
  -r, --recursive             Process subdirectories recursively
  --keep-mkv                  Keep .mkv extension instead of matching original filename
  --log-type TEXT             Log format: 'txt' (default), 'html', 'json', or 'none'
  --log-dir TEXT              Directory for logs (default: %TEMP%/av1-logs)
  --ffmpeg TEXT               Path to ffmpeg executable (overrides AV1_FFMPEG_PATH)
  --ffprobe TEXT              Path to ffprobe executable (overrides AV1_FFPROBE_PATH)
  --no-prompt                 Suppress interactive confirmations
  --no-color                  Disable colored output
  --parallel, -j INT          Files to process simultaneously [default: 1]
  -V, --version               Show version and exit
  --help                      Show full help message and exit
```

### Options (detailed table)
<table>
   <tr><th>Flag</th><th>Description</th></tr>
   <tr><td>--output-dir &lt;TEXT&gt;</td><td>Output directory (defaults to input folder).</td></tr>
   <tr><td>--bitrate &lt;TEXT&gt;</td><td>Override video bitrate (e.g., 2500k, 2m).</td></tr>
   <tr><td>-d, --delete-original</td><td>Auto-delete originals after successful conversion.</td></tr>
   <tr><td>-o, --overwrite</td><td>Overwrite existing output files without prompting.</td></tr>
   <tr><td>--dry-run</td><td>Preview conversion plan without encoding.</td></tr>
   <tr><td>-r, --recursive</td><td>Process subdirectories recursively, preserving structure.</td></tr>
   <tr><td>--keep-mkv</td><td>Keep .mkv extension instead of matching original filename.</td></tr>
   <tr><td>--log-type &lt;TEXT&gt;</td><td>Log format: 'txt', 'html', 'json', or 'none' to disable.</td></tr>
   <tr><td>--log-dir &lt;TEXT&gt;</td><td>Directory for logs (default: %TEMP%/av1-logs).</td></tr>
   <tr><td>--ffmpeg &lt;TEXT&gt;</td><td>Path to ffmpeg executable (overrides env or PATH).</td></tr>
   <tr><td>--ffprobe &lt;TEXT&gt;</td><td>Path to ffprobe executable (overrides env or PATH).</td></tr>
   <tr><td>--no-prompt</td><td>Suppress interactive prompts (useful for automation).</td></tr>
   <tr><td>--no-color</td><td>Disable colored output (useful for logging/piping).</td></tr>
   <tr><td>--parallel, -j &lt;INT&gt;</td><td>Concurrent files to process [experimental, default: 1].</td></tr>
   <tr><td>-V, --version</td><td>Show version and exit.</td></tr>
   <tr><td>--help</td><td>Show full help message and exit.</td></tr>
</table>

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
