# av1

A fast, reliable video batch converter that targets the best available encoder on your system (AV1 on NVIDIA/AMD GPUs when possible, otherwise HEVC or CPU AV1), with conservative defaults to reduce file size by ~35% while preserving quality.

## Features

- **Auto-detects best encoder**: `av1_nvenc` → `av1_amf` → `hevc_nvenc` → `hevc_amf` → `libsvtav1`
- **Smart bitrate selection**: Probes input bitrate and targets ~35% reduction by default, with optional presets for stronger compression
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

# Custom output basename and skip rename back to original name
av1 "C:\Videos\movie.mp4" --output-prepend "draft_" --output-append "_v2"

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
  --no-rename                 Keep encoded output filename; do not restore original basename
  --output-prepend TEXT       Text prepended to output basename (before -CODEC.mkv)
  --output-append TEXT        Text appended to source stem (before -CODEC.mkv)
  --log-type TEXT             Log format: 'txt' (default), 'html', 'json', or 'none'
  --log-dir TEXT              Directory for logs (default: %TEMP%/av1-logs)
  --ffmpeg TEXT               Path to ffmpeg executable (overrides AV1_FFMPEG_PATH)
  --ffprobe TEXT              Path to ffprobe executable (overrides AV1_FFPROBE_PATH)
  --cpu-threads, --cpu-cores INT
                              Logical CPU threads for CPU AV1 encoding [default: 75% of logical CPUs, max: available logical CPUs]
  --prompt-av1                Prompt before re-encoding AV1 files
  --reencode-av1              Re-encode AV1 files without confirmation
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
   <tr><td>--keep-mkv</td><td>Keep .mkv extension instead of matching original filename (implies no post-conversion rename).</td></tr>
   <tr><td>--no-rename</td><td>Keep the encoded output name (e.g. <code>movie-AV1.mkv</code>); do not rename back to the original basename.</td></tr>
   <tr><td>--output-prepend</td><td>Prepend text to the output basename (e.g. <code>draft_</code> → <code>draft_movie-AV1.mkv</code>).</td></tr>
   <tr><td>--output-append</td><td>Append text to the source stem before <code>-CODEC.mkv</code> (e.g. <code>_v2</code> → <code>movie_v2-AV1.mkv</code>). Implies <code>--no-rename</code>.</td></tr>
   <tr><td>--log-type &lt;TEXT&gt;</td><td>Log format: 'txt', 'html', 'json', or 'none' to disable.</td></tr>
   <tr><td>--log-dir &lt;TEXT&gt;</td><td>Directory for logs (default: %TEMP%/av1-logs).</td></tr>
   <tr><td>--ffmpeg &lt;TEXT&gt;</td><td>Path to ffmpeg executable (overrides env or PATH).</td></tr>
   <tr><td>--ffprobe &lt;TEXT&gt;</td><td>Path to ffprobe executable (overrides env or PATH).</td></tr>
   <tr><td>--cpu-threads, --cpu-cores &lt;INT&gt;</td><td>Logical CPU threads dedicated to CPU AV1 encoding. Defaults to 75% of available logical CPUs and rejects values above the available logical CPU count.</td></tr>
   <tr><td>--prompt-av1</td><td>Prompt before re-encoding files that are already AV1.</td></tr>
   <tr><td>--reencode-av1</td><td>Re-encode files that are already AV1 without prompting. Mutually exclusive with <code>--prompt-av1</code>.</td></tr>
   <tr><td>--no-prompt</td><td>Suppress interactive prompts (useful for automation).</td></tr>
   <tr><td>--no-color</td><td>Disable colored output (useful for logging/piping).</td></tr>
   <tr><td>--parallel, -j &lt;INT&gt;</td><td>Concurrent files to process [experimental, default: 1].</td></tr>
   <tr><td>-V, --version</td><td>Show version and exit.</td></tr>
   <tr><td>--help</td><td>Show full help message and exit.</td></tr>
</table>

## How it works

1. **Validates environment**: Checks that `ffmpeg` and `ffprobe` are available (uses PATH or env/CLI overrides with automatic fallback).
2. **Detects best encoder**:
   - **Windows**: NVIDIA AV1 (`av1_nvenc`) → AMD AV1 (`av1_amf`) → NVIDIA HEVC (`hevc_nvenc`) → AMD HEVC (`hevc_amf`) → CPU AV1 (`libsvtav1`)
   - **Linux**: VAAPI AV1 → NVIDIA AV1 (`av1_nvenc`) → VAAPI HEVC → NVIDIA HEVC → CPU AV1
3. **For each video file**:
   - Skips files that are already AV1 by default when AV1 is the active target.
   - Use `--prompt-av1` to ask per file, or `--reencode-av1` to always re-encode them without prompting.
   - Skips if already encoded with the target codec in other cases (optimization).
   - Probes input bitrate and calculates target (~35% reduction by default).
   - Applies safe scaling (max width 1920 by default, maintains aspect ratio, only downsizes sources wider than the active max width).
   - Encodes with VBR using `-b:v` (target), `-maxrate` (peak), `-bufsize` (buffer).
   - Preserves audio channels, re-encodes to Opus (configurable).
   - Writes to temp `.temp.mkv`, atomically swaps on success.
   - Optionally deletes or prompts to delete original; can rename output when converting in-place.
4. **Displays progress**: Nested progress bars showing overall batch progress and per-file encoding progress with FPS/ETA.
5. **Saves logs**: Structured logs (txt/html/json) with per-file metrics, batch summary, and execution timeline.

## Environment Variables

Configure defaults without CLI flags (useful for automation, CI/CD, or system-wide settings):

```powershell
# Ffmpeg/Ffprobe paths (CLI --ffmpeg/--ffprobe take precedence)
$env:AV1_FFMPEG_PATH = "C:\custom\ffmpeg.exe"
$env:AV1_FFPROBE_PATH = "C:\custom\ffprobe.exe"

# Encoding parameters
$env:AV1_AUDIO_BITRATE = "96k"               # Opus audio bitrate (default: 64k)
$env:AV1_MAX_VIDEO_WIDTH = "1280"            # Max output width (default: 1920)
$env:AV1_BITRATE_REDUCTION_FACTOR = "0.6"    # Bitrate factor (default: 0.65, roughly 35% reduction)
$env:AV1_BITRATE_FALLBACK = "1800000"        # Fallback in bps if probe fails (default: 2M)

# Logging and display
$env:AV1_LOG_TYPE = "json"                   # Default log format (default: txt)
$env:AV1_LOG_DIR = "C:\Logs"                 # Default log directory (default: %TEMP%/av1-logs)
$env:AV1_NO_COLOR = "1"                      # Disable colored output (default: enabled)
$env:AV1_NO_PROMPT = "1"                     # Suppress interactive prompts (default: enabled)
$env:AV1_OUTPUT_PREPEND = "draft_"           # Default prepend for output basename
$env:AV1_OUTPUT_APPEND = "_small"             # Default append for output stem (implies no rename)
$env:AV1_NO_RENAME = "1"                      # Same as --no-rename (skip restore to original basename)
```

Example: Automation script with custom defaults
```powershell
$env:AV1_LOG_TYPE = "json"
$env:AV1_NO_PROMPT = "1"
$env:AV1_BITRATE_REDUCTION_FACTOR = "0.6"  # 40% reduction instead of the default ~35%

python .\av1.py "D:\Videos" --recursive --delete-original
# Logs will be JSON, no prompts, and use 40% bitrate reduction
```

## Notes and defaults

- **Pixel format**: `nv12` for hardware encoders, `yuv420p` for CPU (automatically selected).
- **Scaling**: `min(1920, iw)` caps width at 1920px while preserving aspect ratio, so lower-resolution sources are not upscaled; override with `--max-width` or `AV1_MAX_VIDEO_WIDTH`.
- **HEVC compatibility**: Outputs tagged `hvc1` for broader device compatibility.
- **Output container**: `.mkv` with `+faststart` flag for faster playback start.
- **Supported input formats**: `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.m4v`, `.wmv` (requires FFmpeg with WMV/ASF support).
- **Disk space safety**: Requires ~1.5× input file size free in output drive before encoding starts.
- **Audio codec**: Opus at configurable bitrate (default 64k per stream) for smaller files and good quality.
- **Default log location**: `%TEMP%\av1-logs\` on Windows (can override with `--log-dir` or `AV1_LOG_DIR`).
- **Progress display**: Shows real-time FPS, ETA per-file, cumulative bytes saved, and batch timeline.

## Tips

- **Use wildcards** to batch process files matching a pattern: `av1 "episode_*.mkv"`
- **Progress tracking** shows real-time FPS, ETA, file count, elapsed time, and cumulative space saved across nested progress bars.
- **Graceful Ctrl+C handling**: Press `Ctrl+C` once to gracefully finish the current file and display a summary. Press `Ctrl+C` again to force quit.
- **Logging** automatically saves structured logs to `%TEMP%\av1-logs\` (configurable). Use `--log-type json` for automation/parsing or `--log-type html` for styled reports.
- **Automation-friendly**: Combine `--no-prompt`, `--no-color`, and `--log-type json` for unattended batch jobs.
- **Environment overrides**: Set `AV1_*` env vars for system-wide defaults; CLI flags always take precedence.
- Use `--recursive` to process entire folder trees, preserving directory structure when using separate output folder.
- For archival quality, raise the bitrate and avoid strict `--min-shrink`/`--size-preset` caps; CPU AV1 usually produces better compression at the same bitrate.
- If outputs are larger, source may already be efficient. The script warns and lets you choose deletion.
- Start with `--dry-run --recursive` to preview all files before committing to conversion.
- Use `--keep-mkv` to preserve `.mkv` extension when converting in-place (useful for consistent naming).
- Use `--ffmpeg` and `--ffprobe` flags to test different FFmpeg builds without modifying PATH.

## Logging

Logs are automatically saved to `%TEMP%\av1-logs\` with timestamped filenames:

- **Text logs** (`.txt`): Plain text with timestamps and emoji indicators, good for quick review.
- **HTML logs** (`.html`): Styled, clickable, color-coded output for web viewing or email reports.
- **JSON logs** (`.json`): Structured data including per-file metrics (original size, bitrate, duration, FPS, etc.) and batch summary; ideal for scripting/automation.

Example JSON log structure:
```json
{
  "app": "av1",
  "version": "0.3.1",
  "generated": "2025-12-16T14:23:45+00:00",
  "system_platform": "windows",
  "encoder": {
    "encoder": "av1_amf",
    "codec": "av1",
    "hw_type": "amd"
  },
  "events": [
    {
      "ts": "2025-12-16T14:23:46+00:00",
      "level": "info",
      "message": "Detecting Best Available Encoder..."
    },
    {
      "ts": "2025-12-16T14:23:47+00:00",
      "level": "success",
      "message": "file_metrics",
      "data": {
        "file": "video.mp4",
        "encoder": "av1_amf",
        "original_bytes": 54773,
        "new_bytes": 38626,
        "saved_bytes": 16147,
        "saved_percent": 29.48,
        "duration": 2.0
      }
    },
    {
      "ts": "2025-12-16T14:23:50+00:00",
      "level": "success",
      "message": "batch_summary",
      "data": {
        "files_total": 520,
        "files_converted": 515,
        "saved_bytes_total": 8234567,
        "saved_percent_total": 28.5,
        "elapsed_seconds": 1043
      }
    }
  ]
}
```

## Troubleshooting

- **"ffmpeg is not found"** → Install FFmpeg and ensure it's in PATH, or use `--ffmpeg` / `AV1_FFMPEG_PATH` to specify path.
- **"ffprobe is not found"** → Similar to above; tool will auto-fallback to PATH if specified path is invalid.
- **"Insufficient disk space"** → Free space or change `--output-dir` to a drive with more room. Tool validates 1.5× file size before encoding.
- **Hardware encoder not detected** → Update GPU drivers; verify FFmpeg build includes NVENC/AMF. Use `--dry-run` to see which encoder was selected.
- **Output larger than input** → Source may already be highly compressed or incompressible (entropy). Use `--min-shrink`, `--max-output-size`, or a size preset for stronger compression; raise `AV1_BITRATE_REDUCTION_FACTOR` for higher quality.
- **Progress bar crashes with KeyError** → Ensure all `_LOG_EVENTS` fields match the Progress bar columns (should be resolved in latest version).
- **Parallel option disabled** → Currently marked experimental; full support coming soon. Sequential processing is fast enough for most use cases.

## Performance Notes

- **GPU encoding**: Hardware encoders (NVIDIA/AMD) are very fast—typically 2-5× realtime encoding speed. 
- **CPU encoding**: CPU AV1 (`libsvtav1`) is slower (~0.5x realtime) but produces smaller files. By default, it uses 75% of available logical CPUs; override with `--cpu-threads` or `--cpu-cores` when you want stricter limits or full usage.
- **Large batches**: For 500+ files, consider using `--no-prompt`, `--no-color`, and `--log-type json` for minimal overhead.
- **Disk I/O**: Ensure output drive can sustain write speeds; slow I/O will bottleneck encoding speed.

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
