# ============================================================================ #
#                                     av1.py                                   #
# ============================================================================ #
# usage (cross-platform):
# av1 "/path/to/videos" "/path/to/output"  (Linux/Mac)
# av1 "C:\\Videos\\Input" "C:\\Videos\\Output"  (Windows)
# av1 "video.mp4" --delete-original
# av1 "/path/to/videos" -r  (recursive)
# av1 clean "/path/to/videos" -r  (remove stale temp files; same as: av1 --clean "/path/to/videos" -r)
# av1 "/path/to/videos"  (convert: `main` is the default when no subcommand is given)
# av1 help              (list subcommands); av1 help main  (compressor options, like av1 --help)
# av1 version
# python "Python/av1/av1.py" "C:\\Videos\\movie.mp4" --probe  (script path first, input path second)

import os
import subprocess
import shutil
import sys
import json
import platform
import glob
import time
import signal
import threading
import queue
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Callable, Literal, Optional, Tuple

# Force UTF-8 encoding on Windows
if platform.system() == 'Windows' and sys.stdout.isatty() and sys.stderr.isatty():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from rich.console import Console
from rich.markup import escape
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Column, Table
import click
import typer

# ============================================================================ #
#                           APP & CLI CONFIGURATION                            #
# ============================================================================ #
__app_name__ = "av1"
__version__ = "0.3.2"

try:
    from _pybin_build_info import BUILD_TIMESTAMP_UTC as __build_timestamp_utc__
except ImportError:
    __build_timestamp_utc__ = None

console = Console()  # Will be reinitialized in main() if --no-color is set

_CLI_KNOWN_SUBCOMMANDS = frozenset({"clean", "cleanup", "help", "list", "ls", "main", "version"})
# Keep Typer group-only options here. Do not list -h/--help: those should show `main` help
# (compressor flags) since `main` is hidden from the group command list.
_CLI_GROUP_ONLY_FLAGS = frozenset(
    {
        "--install-completion",
        "--show-completion",
    }
)


def _normalize_cli_argv(argv: list[str]) -> list[str]:
    """If the user omits a subcommand, assume `main` (so paths and flags like --clean work without typing `main`)."""
    if not argv:
        return argv
    script, *rest = argv
    if not rest:
        return [script, "main"]
    first = rest[0]
    if first in _CLI_KNOWN_SUBCOMMANDS or first in _CLI_GROUP_ONLY_FLAGS:
        return argv
    return [script, "main", *rest]


app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    rich_markup_mode="rich",  # Enable Rich markup in help output
    epilog=(
        "Default: run the compressor (paths and options go on the command line; no subcommand). "
        "Subcommands: [bold]help[/] [TOPIC] — group or subcommand help; [bold]version[/] — app and ffmpeg info; "
        "[bold]list[/] / [bold]ls[/] — scan for videos and show codec and size; "
        "[bold]clean[/] / [bold]cleanup[/] — remove stale *.temp.mkv files."
    ),
)

# ============================================================================ #
#                        ENCODING CONFIGURATION CONSTANTS                      #
# ============================================================================ #
BITRATE_REDUCTION_FACTOR = 0.5
BITRATE_FALLBACK = 2_000_000
BITRATE_MAXRATE_MULTIPLIER = 1.2
BITRATE_BUFSIZE_MULTIPLIER = 2.0
DEFAULT_CPU_USAGE_PERCENT = 75

# ============================================================================ #
#                         FILE HANDLING CONSTANTS                              #
# ============================================================================ #
SUPPORTED_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".wmv")
TEMP_OUTPUT_SUFFIX = ".temp.mkv"
ROOT_PREVIEW_MAX_WALK_STEPS = 750  # Cap os.walk steps for root-confirm preview (keep huge trees responsive)
MIN_FILE_SIZE_BYTES = 1024  # Skip files smaller than 1KB
DISK_SPACE_SAFETY_MARGIN = 1.5  # Require 1.5x file size in free space

# ============================================================================ #
#                        ENCODING PARAMETER CONSTANTS                          #
# ============================================================================ #
AUDIO_BITRATE = "64k"  # Opus audio bitrate per stream
MAX_VIDEO_WIDTH = 1920  # Maximum video width (maintains aspect ratio)
VIDEO_BITRATE_ESTIMATE_FACTOR = 0.9  # Factor to estimate video-only bitrate from total
RECOMMENDED_BITRATE_MARGIN = 1.15  # Consider within +15% of recommended as "at target"
RECOMMENDED_BITRATE_MIN = 400_000  # Clamp recommended bitrate floor
RECOMMENDED_BITRATE_MAX = 20_000_000  # Clamp recommended bitrate ceiling
PROGRESS_TIMEOUT = 10  # Timeout for ffprobe operations (seconds)
ENCODER_TEST_TIMEOUT = 5  # Timeout for encoder detection tests (seconds)
FFMPEG_STALL_TIMEOUT = 300  # Abort ffmpeg if it emits no progress/output for this many seconds
PROMPT_YES_NO_ALL = "[Y/n/a] (y=yes, n=no, a=all): "
SIZE_PRESETS: dict[str, dict[str, object]] = {
    "light": {
        "min_shrink_percent": 35.0,
        "max_video_width": 1920,
    },
    "balanced": {
        "min_shrink_percent": 55.0,
        "max_video_width": 1280,
    },
    "aggressive": {
        "min_shrink_percent": 70.0,
        "max_video_width": 960,
    },
}

# ============================================================================ #
#                           ENVIRONMENT OVERRIDES                             #
# ============================================================================ #
# Environment variables to tweak behavior without changing CLI:
#   AV1_AUDIO_BITRATE, AV1_MAX_VIDEO_WIDTH, AV1_BITRATE_REDUCTION_FACTOR,
#   AV1_BITRATE_FALLBACK, AV1_MAX_OUTPUT_SIZE, AV1_MIN_SHRINK, AV1_CPU_THREADS,
#   AV1_NO_COLOR, AV1_NO_PROMPT, AV1_HIDE_FILENAMES, AV1_LOG_TYPE, AV1_LOG_DIR,
#   AV1_FFMPEG_PATH, AV1_FFPROBE_PATH, AV1_FFMPEG_FALLBACK, AV1_IGNORE_LIBVA_WARNING,
#   AV1_FFMPEG_STALL_TIMEOUT

def _env_bool(val: str) -> bool:
    return str(val).strip().lower() in {"1", "true", "yes", "on"}

FFMPEG_CMD = os.getenv("AV1_FFMPEG_PATH") or "ffmpeg"
FFPROBE_CMD = os.getenv("AV1_FFPROBE_PATH") or "ffprobe"

try:
    _env_val = os.getenv("AV1_AUDIO_BITRATE")
    if _env_val:
        AUDIO_BITRATE = _env_val
    _env_val = os.getenv("AV1_MAX_VIDEO_WIDTH")
    if _env_val:
        MAX_VIDEO_WIDTH = int(_env_val)
    _env_val = os.getenv("AV1_BITRATE_REDUCTION_FACTOR")
    if _env_val:
        BITRATE_REDUCTION_FACTOR = float(_env_val)
    _env_val = os.getenv("AV1_BITRATE_FALLBACK")
    if _env_val:
        BITRATE_FALLBACK = int(_env_val)
    _env_val = os.getenv("AV1_FFMPEG_STALL_TIMEOUT")
    if _env_val:
        FFMPEG_STALL_TIMEOUT = int(_env_val)
except Exception:
    # Ignore invalid env overrides and proceed with defaults
    pass

# ============================================================================ #
#                          SYSTEM STATE VARIABLES                              #
# ============================================================================ #
SYSTEM_PLATFORM = platform.system().lower()  # 'windows', 'linux', 'darwin'
ACTIVE_ENCODER = {  # Detected encoder info (CPU fallback as default)
    "encoder": "libsvtav1",  # Encoder name
    "codec": "av1",  # av1 or hevc
    "hw_type": "cpu"  # nvidia, amd, cpu, or vaapi
}

# ============================================================================ #
#                           RUNTIME STATE FLAGS                                #
# ============================================================================ #
_SUPPRESS_OUTPUT = False  # Suppress cprint output during conversions
_PROGRESS_CONTEXT = None  # Active progress context manager
_USER_CANCELLED = False  # User pressed Ctrl+C
_LOG_MESSAGES = []  # Store all messages for file logging
_LOGGER = None  # Logger instance (unused, kept for compatibility)
_LOG_EVENTS: list[dict] = []  # Structured events for JSON logging
_NO_COLOR = False  # Disable colors when True
_NO_PROMPT = False  # Suppress interactive prompts
_HIDE_FILENAMES = False  # Redact media filenames from console output when True
_STARTUP_SUMMARY_EMITTED = False  # Avoid duplicate startup summaries on internal re-entry
_AUTO_REENCODE_AV1 = False  # Remember "all" choice when confirming AV1 re-encodes
_AUTO_OVERWRITE_EXISTING = False  # Remember "all" for deleting existing outputs before encode
_AUTO_RENAME_TO_ORIGINAL = False  # Remember "all" for restoring original filename after delete

# ============================================================================ #
#                          VERSION FLAG CALLBACK                               #
# ============================================================================ #
def _format_build_timestamp(build_timestamp: Optional[str]) -> Optional[str]:
    if not build_timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(build_timestamp.replace("Z", "+00:00"))
        return parsed.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        return build_timestamp


def _version_callback(value: bool) -> None:
    """Display version and exit."""
    if value:
        py_exec = sys.executable
        py_ver = platform.python_version()
        typer.echo(f"{__app_name__} {__version__}")
        typer.echo(f"Python: {py_exec} ({py_ver})")
        build_timestamp = _format_build_timestamp(__build_timestamp_utc__)
        if build_timestamp:
            typer.echo(f"Built: {build_timestamp}")
        
        # Get ffmpeg version
        try:
            global FFMPEG_CMD
            # Validate ffmpeg path first
            ffmpeg_ok = shutil.which(FFMPEG_CMD) or (os.path.exists(FFMPEG_CMD) and os.path.isfile(FFMPEG_CMD))
            if not ffmpeg_ok:
                path_ffmpeg = shutil.which("ffmpeg")
                if path_ffmpeg:
                    FFMPEG_CMD = path_ffmpeg
            
            # Get version
            version_cmd = [FFMPEG_CMD, "-version"]
            result = subprocess.run(version_cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Parse version from first line (e.g., "ffmpeg version 6.1.1-3ubuntu5" or "ffmpeg version N-122320-g38e89fe502-20260101")
                first_line = result.stdout.split('\n')[0] if result.stdout else ""
                if "version" in first_line.lower():
                    # Extract version string - typically "ffmpeg version X.Y.Z" or "ffmpeg version N-XXXXX"
                    parts = first_line.split()
                    if len(parts) >= 3 and parts[0].lower() == "ffmpeg" and parts[1].lower() == "version":
                        ffmpeg_version = parts[2]
                        # Shorten git versions (N-122320-g38e89fe502-20260101 -> N-122320)
                        if ffmpeg_version.startswith("N-") and "-g" in ffmpeg_version:
                            ffmpeg_version = ffmpeg_version.split("-g")[0]
                        typer.echo(f"FFmpeg: {FFMPEG_CMD} ({ffmpeg_version})")
        except Exception:
            # If we can't get version, just show the path
            try:
                typer.echo(f"FFmpeg: {FFMPEG_CMD}")
            except Exception:
                pass
        
        # Attempt to run a lightweight hardware encoder detection and print result.
        try:
            # Use check_ffmpeg to populate ACTIVE_ENCODER; catch failures to avoid exiting.
            try:
                check_ffmpeg()
            except Exception:
                # If check_ffmpeg raised (missing ffmpeg/ffprobe or other), report and continue
                cprint("⚠️  Could not run encoder detection (ffmpeg/ffprobe missing or check failed).", "warning")

            # Print detected encoder summary
            try:
                enc = ACTIVE_ENCODER.get("encoder") if isinstance(ACTIVE_ENCODER, dict) else None
                hw = ACTIVE_ENCODER.get("hw_type") if isinstance(ACTIVE_ENCODER, dict) else None
                if enc:
                    typer.echo(f"Detected encoder: {enc} (type: {hw})")
            except Exception:
                pass

        finally:
            raise typer.Exit()


def _show_examples() -> None:
    """Display formatted examples."""
    examples = """
    EXAMPLES:
      av1 "C:\\Videos"                          Convert all videos in folder
      av1 "C:\\Videos\\movie.mp4" -d            Convert single file, delete original  
      av1 "episode_*.mkv"                       Wildcard pattern conversion
      av1 "C:\\Input" "C:\\Output" -o            Batch with custom output folder
      av1 "C:\\Videos" -r --log-type html       Recursive with HTML logging
      av1 "C:\\Videos" -r --dry-run              Preview changes without converting
      av1 "C:\\Videos\\movie.mp4" --probe       Probe a file without converting
      python "Python/av1/av1.py" "C:\\Videos\\movie.mp4" --probe
                                                Run directly: script path first, input path second
    
    NOTES:
      • The positional path after `av1` is the input video/file/folder path
      • Logs saved to ./logs/ by default
      • Press Ctrl+C once to finish current file and exit gracefully
      • Use -h or --help for complete option list
    """
    cprint(examples, "info")


def _format_saved(bytes_amount: float) -> str:
    """Pretty-print saved bytes as KB/MB/GB for progress columns."""
    if bytes_amount >= 1024 ** 3:
        return f"{bytes_amount / (1024 ** 3):.2f} GB"
    if bytes_amount >= 1024 ** 2:
        return f"{bytes_amount / (1024 ** 2):.1f} MB"
    if bytes_amount >= 1024:
        return f"{bytes_amount / 1024:.1f} KB"
    return "0"

def _format_size(bytes_amount: float) -> str:
    """Pretty-print file size as KB/MB/GB for progress columns."""
    if bytes_amount >= 1024 ** 3:
        return f"{bytes_amount / (1024 ** 3):.2f} GB"
    if bytes_amount >= 1024 ** 2:
        return f"{bytes_amount / (1024 ** 2):.2f} MB"
    if bytes_amount >= 1024:
        return f"{bytes_amount / 1024:.1f} KB"
    return f"{bytes_amount} B"


def _sum_existing_file_sizes(paths: list[str]) -> tuple[int, int]:
    """Sum on-disk sizes for paths that stat successfully. Returns (total_bytes, ok_count)."""
    total = 0
    n_ok = 0
    for p in paths:
        try:
            total += os.path.getsize(p)
            n_ok += 1
        except OSError:
            pass
    return total, n_ok


def _format_duration(seconds: Optional[float]) -> str:
    """Pretty-print seconds as HH:MM:SS."""
    if not isinstance(seconds, (int, float)) or seconds <= 0:
        return "unknown"
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_fps_display(fps: Optional[float]) -> str:
    """Pretty-print FPS with a stable precision."""
    if not isinstance(fps, (int, float)) or float(fps) <= 0:
        return "unknown"
    return f"{float(fps):.2f}"


def _format_bitrate_display(bitrate: Optional[int]) -> str:
    """Pretty-print bitrate using Mbps/kbps as appropriate."""
    if not isinstance(bitrate, (int, float)) or float(bitrate) <= 0:
        return "unknown"
    bitrate_value = float(bitrate)
    if bitrate_value >= 1_000_000:
        return f"{bitrate_value / 1_000_000:.2f} Mbps"
    if bitrate_value >= 1_000:
        return f"{bitrate_value / 1_000:.0f} kbps"
    return f"{int(bitrate_value)} bps"


def _build_media_info(stream_info: dict) -> str:
    """Build a compact media metadata summary for logs and status output."""
    width = stream_info.get("width")
    height = stream_info.get("height")
    duration = stream_info.get("duration")
    fps = stream_info.get("fps")
    bitrate = stream_info.get("bitrate")
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        resolution = f"{width}x{height}"
    else:
        resolution = "unknown"
    return (
        f"{resolution} | length {_format_duration(duration)} | "
        f"fps {_format_fps_display(fps)} | bitrate {_format_bitrate_display(bitrate)}"
    )


def _format_timecode(seconds: Optional[float]) -> str:
    """Pretty-print media timestamps compactly as MM:SS or HH:MM:SS."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "unknown"
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _format_elapsed(seconds: int) -> str:
    """Pretty-print elapsed seconds compactly for batch status lines."""
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def _format_eta_seconds(seconds: Optional[float]) -> str:
    """Pretty-print ETA values compactly for progress displays."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "calculating..."
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def _format_progress_clock(current_seconds: Optional[float], total_seconds: Optional[float]) -> str:
    """Render labeled media progress for the current file."""
    current_value = 0.0
    if isinstance(current_seconds, (int, float)) and current_seconds > 0:
        current_value = float(current_seconds)
    if not isinstance(total_seconds, (int, float)) or total_seconds <= 0:
        if current_value <= 0:
            return "Encoding..."
        return f"Video {_format_timecode(current_value)} encoded"
    current_value = min(current_value, float(total_seconds))
    return f"Video {_format_timecode(current_value)} of {_format_timecode(total_seconds)}"


def _parse_ffmpeg_out_time(value: str) -> Optional[float]:
    """Parse ffmpeg progress timestamps like HH:MM:SS.microseconds."""
    try:
        hours, minutes, seconds = value.strip().split(":", 2)
        return (int(hours) * 3600) + (int(minutes) * 60) + float(seconds)
    except Exception:
        return None


def _parse_ffmpeg_speed(value: str) -> Optional[float]:
    """Parse ffmpeg speed strings like '2.35x'."""
    try:
        cleaned = value.strip().lower()
        if cleaned.endswith("x"):
            cleaned = cleaned[:-1]
        speed = float(cleaned)
        return speed if speed > 0 else None
    except Exception:
        return None


def _format_rate_display(fps_value: str, speed_value: str) -> str:
    """Combine fps and encoder speed into a compact status field."""
    parts = []
    try:
        fps_number = float(fps_value)
        if fps_number > 0:
            parts.append(f"{int(fps_number)} fps")
    except Exception:
        pass
    speed_number = _parse_ffmpeg_speed(speed_value)
    if speed_number:
        parts.append(f"{speed_number:.2f}x")
    return " | ".join(parts)


def _display_path(
    path: str,
    *,
    base_path: Optional[str] = None,
    full_path: bool = False,
    fallback_label: str = "filename hidden",
) -> str:
    """Format user-facing paths while honoring filename redaction."""
    if _HIDE_FILENAMES:
        return fallback_label
    if full_path:
        try:
            return os.path.normpath(os.path.abspath(path))
        except Exception:
            return path
    if base_path:
        try:
            return os.path.relpath(path, base_path)
        except Exception:
            pass
    return os.path.basename(path)


def _path_console_log(
    path: str,
    *,
    base_path: Optional[str] = None,
    fallback_label: str = "filename hidden",
) -> tuple[str, str]:
    """Return (console_path, log_path): short display vs canonical absolute for log files."""
    short = _display_path(path, base_path=base_path, fallback_label=fallback_label)
    long = _display_path(path, full_path=True, fallback_label=fallback_label)
    return short, long


def _append_log_directory_header(directory: str) -> None:
    """Append a multi-line folder separator to file logs only (not the console)."""
    shown = _display_path(directory, full_path=True, fallback_label="folder")
    sep = "-" * 72
    block = f"{sep}\nDirectory: {shown}\n{sep}"
    _LOG_MESSAGES.append(block)
    try:
        _LOG_EVENTS.append({
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "level": "info",
            "message": "log_directory",
            "data": {"directory": shown},
        })
    except Exception:
        pass


def _is_root_like_directory_path(path: str) -> bool:
    """
    True when path points at a filesystem, drive, or UNC share root (very broad scan targets).
    Used to ask for an extra confirmation before convert/probe/clean.
    """
    try:
        expanded = os.path.normpath(
            os.path.normcase(os.path.expandvars(os.path.expanduser(path)))
        )
    except Exception:
        return False
    if platform.system() == "Windows":
        p = expanded.replace("/", "\\")
        if p.startswith("\\\\?\\UNC\\"):
            p = "\\\\" + p[7:]
        elif p.startswith("\\\\?\\"):
            inner = p[4:]
            drive, tail = os.path.splitdrive(inner)
            return bool(drive) and tail in ("\\", "/", "")
        drive, tail = os.path.splitdrive(p)
        if drive and tail in ("\\", "/", ""):
            return True
        if p.startswith("\\\\"):
            parts = [x for x in p[2:].split("\\") if x]
            return len(parts) == 2
        return False
    return expanded == "/"


def _count_shallow_matches(root: str, *, mode: Literal["video", "temp"]) -> int:
    """Count matching files in the root directory only (non-recursive)."""
    n = 0
    try:
        for fn in os.listdir(root):
            fp = os.path.join(root, fn)
            if not os.path.isfile(fp):
                continue
            if mode == "video":
                if fn.lower().endswith(SUPPORTED_EXTENSIONS):
                    n += 1
            elif fn.lower().endswith(TEMP_OUTPUT_SUFFIX):
                n += 1
    except OSError:
        return 0
    return n


def _preview_recursive_work_dirs(
    root: str,
    *,
    mode: Literal["video", "temp"],
    max_walk_steps: int = ROOT_PREVIEW_MAX_WALK_STEPS,
) -> tuple[list[str], int, int, bool]:
    """
    Walk under root up to max_walk_steps directory visits.
    Returns (sorted dirs that contain ≥1 match, total matching files, steps used, truncated).
    """
    dirs_with_hits: set[str] = set()
    total_matches = 0
    steps = 0
    truncated = False

    def _file_matches(name: str) -> bool:
        low = name.lower()
        if mode == "video":
            return low.endswith(SUPPORTED_EXTENSIONS)
        return low.endswith(TEMP_OUTPUT_SUFFIX)

    try:
        for dirpath, _dirnames, filenames in os.walk(root):
            steps += 1
            if steps > max_walk_steps:
                truncated = True
                break
            hit_here = False
            for fn in filenames:
                if _file_matches(fn):
                    hit_here = True
                    total_matches += 1
            if hit_here:
                dirs_with_hits.add(os.path.normpath(dirpath))
    except OSError:
        return ([], 0, steps, truncated)

    return (sorted(dirs_with_hits), total_matches, steps, truncated)


def _confirm_root_like_input_paths(
    input_paths: list[str],
    *,
    intent: Literal["convert", "probe", "clean", "list"],
    recursive: bool = False,
) -> None:
    """If any existing directory argument is a volume/share root, require explicit confirmation."""
    if _NO_PROMPT:
        return
    env_np = os.getenv("AV1_NO_PROMPT")
    if env_np and _env_bool(env_np):
        return
    roots: list[str] = []
    for raw in input_paths:
        if not raw.strip():
            continue
        if "*" in raw or "?" in raw:
            continue
        try:
            cand = os.path.abspath(os.path.expandvars(os.path.expanduser(raw)))
        except Exception:
            continue
        if not os.path.isdir(cand):
            continue
        if _is_root_like_directory_path(cand):
            roots.append(os.path.normpath(cand))
    if not roots:
        return
    unique = sorted(set(roots))
    shown = "\n".join(f"  • {_display_path(r, full_path=True, fallback_label='path')}" for r in unique)
    action = {
        "convert": "convert, dry-run, or recurse into",
        "probe": "probe media under",
        "list": "list media under",
        "clean": "delete stale *.temp.mkv under",
    }[intent]
    mode: Literal["video", "temp"] = "temp" if intent == "clean" else "video"
    kind = "video" if mode == "video" else f"*{TEMP_OUTPUT_SUFFIX}"

    cprint(
        "⚠️  One or more inputs look like a drive or share root (very broad scope).",
        "warning",
    )
    cprint(f"This command would {action}:\n{shown}", "warning")

    if recursive:
        cprint(
            f"Quick preview where --recursive may touch {kind} files "
            f"(first {ROOT_PREVIEW_MAX_WALK_STEPS} folders visited per root; full run can reach farther):",
            "info",
        )
        for r in unique:
            root_disp = _display_path(r, full_path=True, fallback_label="path")
            dlist, nfiles, steps, trunc = _preview_recursive_work_dirs(r, mode=mode)
            cprint(f"  [{root_disp}]", "info")
            if nfiles == 0 and not trunc:
                cprint("    No matching files under this path in the preview walk.", "info")
            elif nfiles == 0 and trunc:
                cprint(
                    f"    No matches in the first {steps} folders visited (preview stopped early).",
                    "info",
                )
            else:
                tail = " (preview partial — more folders exist)" if trunc else ""
                cprint(
                    f"    {nfiles} matching file(s) in {len(dlist)} folder(s); "
                    f"visited {steps} folder(s){tail}.",
                    "info",
                )
                for d in dlist[:30]:
                    cprint(f"      • {_display_path(d, full_path=True, fallback_label='path')}", "info")
                if len(dlist) > 30:
                    cprint(f"      … and {len(dlist) - 30} more folders with matches", "info")
    else:
        cprint(
            "Without --recursive, only files directly inside each root folder are considered (no subfolders).",
            "info",
        )
        for r in unique:
            root_disp = _display_path(r, full_path=True, fallback_label="path")
            n = _count_shallow_matches(r, mode=mode)
            cprint(f"  [{root_disp}] ~{n} matching file(s) in this folder only.", "info")

    resp = safe_input(
        "Type YES (all caps) to continue, or anything else to cancel: ",
        message="",
    ).strip()
    if resp != "YES":
        cprint("Aborted.", "info")
        raise typer.Exit(code=1)


def _display_batch_item(file_path: str, input_path: str, recursive: bool, current: int, total: int) -> str:
    """Format the current batch item label for progress and summaries."""
    if _HIDE_FILENAMES:
        return f"file {current}/{total} (hidden)"
    if recursive:
        return _display_path(file_path, base_path=input_path, fallback_label="file")
    return _display_path(file_path, fallback_label="file")


def _default_cpu_threads() -> int:
    """Use 75% of available logical CPUs for CPU encoding by default."""
    logical_cpus = _logical_cpu_count()
    return max(1, (logical_cpus * DEFAULT_CPU_USAGE_PERCENT + 99) // 100)


def _logical_cpu_count() -> int:
    """Return the available logical CPU count with a safe minimum."""
    return max(1, os.cpu_count() or 1)


def _resolve_cpu_threads(requested_threads: Optional[int]) -> int:
    """Validate and resolve the effective CPU thread count."""
    if requested_threads is None:
        return _default_cpu_threads()
    return max(1, int(requested_threads))


def _resolve_executable_path(configured_path: str, fallback_name: str) -> Optional[str]:
    """Resolve an executable from a configured path or PATH lookup."""
    if shutil.which(configured_path):
        return configured_path
    if os.path.exists(configured_path) and os.path.isfile(configured_path):
        return configured_path
    return shutil.which(fallback_name)


def _print_startup_summary(
    input_paths: list[str],
    *,
    output_dir: Optional[str],
    bitrate: Optional[str],
    max_output_size: Optional[str],
    min_shrink_percent: Optional[float],
    force: bool,
    delete_original: bool,
    rename_original: bool,
    overwrite: bool,
    dry_run: bool,
    recursive: bool,
    keep_mkv: bool,
    log_type: str,
    log_dir: Optional[str],
    ffmpeg: Optional[str],
    ffprobe: Optional[str],
    no_color: bool,
    no_prompt: bool,
    hide_filenames: bool,
    prompt_av1: bool,
    reencode_av1: bool,
    probe_only: bool,
    cpu_threads_requested: Optional[int],
    effective_cpu_threads: int,
    requested_parallel: int,
    effective_parallel: int,
    size_preset: Optional[str],
    max_video_width: int,
) -> None:
    """Print a concise startup confirmation of active inputs and options."""
    global _STARTUP_SUMMARY_EMITTED
    if _STARTUP_SUMMARY_EMITTED:
        return
    if not input_paths:
        return

    if len(input_paths) == 1:
        input_summary = _display_path(input_paths[0], full_path=True, fallback_label="1 input path hidden")
    else:
        input_summary = f"{len(input_paths)} input paths"

    options: list[str] = []
    if output_dir:
        options.append(f"output-dir={_display_path(output_dir, full_path=True, fallback_label='hidden')}")
    if bitrate:
        options.append(f"bitrate={bitrate}")
    if max_output_size:
        options.append(f"max-output-size={max_output_size}")
    if min_shrink_percent is not None:
        options.append(f"min-shrink={min_shrink_percent:g}")
    if size_preset:
        options.append(f"size-preset={size_preset}")
    if max_video_width != MAX_VIDEO_WIDTH:
        options.append(f"max-width={max_video_width}")
    if force:
        options.append("force")
    if delete_original:
        options.append("delete-original")
    if rename_original:
        options.append("rename-original")
    if overwrite:
        options.append("overwrite")
    if dry_run:
        options.append("dry-run")
    if recursive:
        options.append("recursive")
    if keep_mkv:
        options.append("keep-mkv")
    if log_type and log_type.lower() != "txt":
        options.append(f"log-type={log_type}")
    if log_dir:
        options.append(f"log-dir={_display_path(log_dir, full_path=True, fallback_label='hidden')}")
    if ffmpeg:
        options.append(f"ffmpeg={_display_path(ffmpeg, full_path=True, fallback_label='hidden')}")
    if ffprobe:
        options.append(f"ffprobe={_display_path(ffprobe, full_path=True, fallback_label='hidden')}")
    if no_color:
        options.append("no-color")
    if no_prompt:
        options.append("no-prompt")
    if hide_filenames:
        options.append("hide-filenames")
    if prompt_av1:
        options.append("prompt-av1")
    if reencode_av1:
        options.append("reencode-av1")
    if probe_only:
        options.append("probe-only")
    if cpu_threads_requested is None:
        options.append(f"cpu-threads={effective_cpu_threads} (default {DEFAULT_CPU_USAGE_PERCENT}% logical CPUs)")
    else:
        options.append(f"cpu-threads={effective_cpu_threads}")
    if requested_parallel != 1:
        if effective_parallel != requested_parallel:
            options.append(f"parallel={effective_parallel} (requested {requested_parallel})")
        else:
            options.append(f"parallel={effective_parallel}")

    cprint("Startup configuration:", "info")
    cprint(f"   Input:  {input_summary}", "info")
    if options:
        cprint(f"   Flags:  {', '.join(options)}", "info")
    else:
        cprint("   Flags:  defaults", "info")
    _STARTUP_SUMMARY_EMITTED = True


def _resolve_size_preset(size_preset: Optional[str]) -> tuple[Optional[str], Optional[dict[str, object]]]:
    """Resolve and validate a named size preset."""
    if not size_preset:
        return None, None
    normalized = str(size_preset).strip().lower()
    preset = SIZE_PRESETS.get(normalized)
    if preset is None:
        valid = ", ".join(sorted(SIZE_PRESETS.keys()))
        cprint(f"Unknown --size-preset {size_preset!r}. Choose one of: {valid}.", "error")
        raise typer.Exit(code=1)
    return normalized, dict(preset)


def _parse_byte_size(spec: str) -> Optional[int]:
    """
    Parse a human-readable size to bytes: '10M', '10MB', '500k', '1G', or plain integer bytes.
    """
    if not spec or not str(spec).strip():
        return None
    s = str(spec).strip().lower().replace(" ", "")
    suffix_map = (
        ("tb", 1024 ** 4),
        ("gb", 1024 ** 3),
        ("mb", 1024 ** 2),
        ("kb", 1024),
        ("t", 1024 ** 4),
        ("g", 1024 ** 3),
        ("m", 1024 ** 2),
        ("k", 1024),
    )
    for suffix, mult in suffix_map:
        if s.endswith(suffix):
            num = s[: -len(suffix)]
            try:
                return int(float(num) * mult)
            except ValueError:
                return None
    try:
        return int(float(s))
    except ValueError:
        return None


def _audio_bitrate_bps() -> int:
    """Opus/audio bitrate from AUDIO_BITRATE (e.g. '64k') as bits per second."""
    ab = str(AUDIO_BITRATE).strip().lower()
    try:
        if ab.endswith("m"):
            return int(float(ab[:-1]) * 1_000_000)
        if ab.endswith("k"):
            return int(float(ab[:-1]) * 1_000)
        return int(float(ab))
    except ValueError:
        return 64_000


def _video_bps_cap_for_max_file_bytes(
    max_file_bytes: int,
    duration_sec: float,
    audio_bps: int,
) -> Optional[int]:
    """
    Approximate upper bound on video bitrate so total muxed size stays under max_file_bytes.
    Uses duration and audio bitrate; leaves a small headroom for container overhead.
    """
    if max_file_bytes <= 0 or duration_sec <= 0:
        return None
    safe_bytes = max(1, int(max_file_bytes * 0.97))
    total_bps = (safe_bytes * 8) / duration_sec
    video_bps = int(total_bps) - audio_bps
    return max(1, video_bps)


def apply_output_size_bitrate_caps(
    target_bitrate_int: int,
    *,
    input_file_bytes: int,
    duration_sec: Optional[float],
    input_stream_bps: Optional[int],
    max_output_bytes: Optional[int],
    min_shrink_percent: Optional[float],
) -> Tuple[int, list[str]]:
    """
    Lower target video bitrate to satisfy --max-output-size and/or --min-shrink when possible.
    Returns (adjusted_bps, list of short reasons for logging).
    """
    notes: list[str] = []
    caps: list[int] = []
    d = float(duration_sec) if isinstance(duration_sec, (int, float)) and duration_sec > 0 else 0.0
    audio_bps = _audio_bitrate_bps()

    if max_output_bytes is not None and max_output_bytes > 0:
        if d > 0:
            c = _video_bps_cap_for_max_file_bytes(max_output_bytes, d, audio_bps)
            if c is not None:
                caps.append(c)
                notes.append(f"max output {_format_size(float(max_output_bytes))}")
        else:
            if not _SUPPRESS_OUTPUT:
                cprint(
                    "--max-output-size ignored (duration unknown); use a file with readable length metadata.",
                    "warning",
                )

    if min_shrink_percent is not None and 0 < min_shrink_percent < 100:
        max_bytes = int(input_file_bytes * (1.0 - min_shrink_percent / 100.0))
        if d > 0 and max_bytes > 0:
            c = _video_bps_cap_for_max_file_bytes(max_bytes, d, audio_bps)
            if c is not None:
                caps.append(c)
                notes.append(f"≥{min_shrink_percent:.0f}% shrink (≤{_format_size(float(max_bytes))})")
        elif isinstance(input_stream_bps, int) and input_stream_bps > 0:
            # No duration: approximate from probed video bitrate only
            factor = 1.0 - min_shrink_percent / 100.0
            caps.append(max(1, int(input_stream_bps * factor)))
            notes.append(f"≥{min_shrink_percent:.0f}% shrink (bitrate heuristic, duration unknown)")
        else:
            if not _SUPPRESS_OUTPUT:
                cprint(
                    "--min-shrink ignored (need duration or video bitrate from probe).",
                    "warning",
                )

    if not caps:
        return target_bitrate_int, []

    effective = min(caps)
    if effective < target_bitrate_int:
        return effective, notes
    return target_bitrate_int, []


def _truncate_middle(text: str, max_length: int = 60) -> str:
    """Shorten long paths so progress rows stay on one terminal line."""
    if len(text) <= max_length:
        return text
    if max_length <= 3:
        return text[:max_length]
    keep = (max_length - 3) // 2
    return f"{text[:keep]}...{text[-(max_length - 3 - keep):]}"


def _console_for_progress() -> Console:
    """Rich Progress console: same color mode as the app, but no auto number/URL highlighting."""
    # Rich stores force_terminal on _force_terminal (no public .force_terminal); PyInstaller builds hit that.
    force_terminal = getattr(console, "force_terminal", None)
    if force_terminal is None:
        force_terminal = getattr(console, "_force_terminal", None)
    return Console(
        file=console.file,
        no_color=console.no_color,
        force_terminal=force_terminal,
        highlight=False,
    )


def _progress_field(value: str) -> str:
    """Escape dynamic progress cell text so characters like '[' never parse as Rich markup."""
    return escape(value) if value else ""


def _styled_filename(label: str) -> str:
    """Render filenames/paths with a consistent color everywhere."""
    return f"[bold cyan]{escape(label)}[/]"


def _styled_progress_filename(label: str) -> str:
    """Paths/filenames in progress: one color; metadata columns use other colors (never bold cyan)."""
    return _styled_filename(label)


def _build_progress(transient: bool, batch_mode: bool = False) -> Progress:
    """Create a progress layout that avoids wrapping in narrow terminals."""
    description_column = Column(
        ratio=2 if batch_mode else 1,
        min_width=24 if batch_mode else None,
        no_wrap=True,
        overflow="ellipsis",
    )
    columns = [
        SpinnerColumn(),
        TextColumn(
            "[progress.description]{task.description}",
            table_column=description_column,
        ),
        BarColumn(bar_width=40 if batch_mode else None),
        TaskProgressColumn(),
    ]

    # Metadata columns: colorized for readability; avoid cyan so filenames (bold cyan) stay distinct.
    if batch_mode:
        columns.extend(
            [
                TextColumn(
                    "[magenta]{task.fields[progress_text]}",
                    table_column=Column(no_wrap=True),
                ),
                TextColumn(
                    "[green]Saved: {task.fields[saved]}",
                    table_column=Column(no_wrap=True),
                ),
                TextColumn(
                    "[blue]Size: {task.fields[size]}",
                    table_column=Column(no_wrap=True),
                ),
                TextColumn(
                    "[yellow]{task.fields[eta]}",
                    table_column=Column(no_wrap=True),
                ),
            ]
        )
    else:
        columns.extend(
            [
                TextColumn(
                    "[magenta]{task.fields[fps]}",
                    table_column=Column(no_wrap=True),
                ),
                TextColumn(
                    "[yellow]{task.fields[eta]}",
                    table_column=Column(no_wrap=True),
                ),
                TextColumn(
                    "[blue]Size: {task.fields[size]}",
                    table_column=Column(no_wrap=True),
                ),
                TextColumn(
                    "[green]Saved: {task.fields[saved]}",
                    table_column=Column(no_wrap=True),
                ),
            ]
        )

    return Progress(*columns, transient=transient, expand=True, console=_console_for_progress())


def _format_batch_progress_description(current: int, total: int, _elapsed_seconds: int, current_item: str) -> str:
    """Build a compact batch progress description for the terminal."""
    if current_item == "waiting...":
        return f"[dim]{escape(current_item)} ({current}/{total})[/]"
    short_item = _truncate_middle(current_item, 52)
    return f"{_styled_progress_filename(short_item)} [yellow]({current}/{total})[/]"


def _format_batch_elapsed_text(elapsed_seconds: int) -> str:
    """Render elapsed batch runtime for the overall progress row."""
    return f"Elapsed: {_format_elapsed(max(elapsed_seconds, 0))}"


def _estimate_batch_eta_seconds(completed_value: float, total_items: int, elapsed_seconds: int) -> Optional[int]:
    """Estimate remaining batch time from overall completion fraction."""
    if total_items <= 0 or elapsed_seconds <= 0 or completed_value <= 0:
        return None
    progress_fraction = min(max(float(completed_value) / float(total_items), 0.0), 1.0)
    if progress_fraction >= 1.0:
        return 0
    remaining_seconds = elapsed_seconds * (1.0 - progress_fraction) / progress_fraction
    return max(int(remaining_seconds), 0)


def _format_batch_eta_text(completed_value: float, total_items: int, elapsed_seconds: int) -> str:
    """Render batch ETA text for the overall progress row."""
    eta_seconds = _estimate_batch_eta_seconds(completed_value, total_items, elapsed_seconds)
    if eta_seconds is None or eta_seconds <= 0:
        return ""
    return f"ETA: {_format_eta_seconds(eta_seconds)}"


def _format_file_progress_description(file_label: str, current: Optional[int] = None, total: Optional[int] = None) -> str:
    """Build a per-file progress label, optionally including batch position."""
    short_label = _truncate_middle(file_label, 48)
    branch = "[dim]  └─[/]"
    if current is not None and total is not None and total > 0:
        return f"{branch} {_styled_progress_filename(short_label)} [yellow]({current}/{total})[/]"
    return f"{branch} [dim]Encoding[/] {_styled_progress_filename(short_label)}"


def _parse_ffprobe_fraction(value: str) -> Optional[float]:
    """Parses FFprobe fraction values like '30000/1001' into float FPS."""
    try:
        if not value or value == "0/0":
            return None
        if "/" in value:
            num, den = value.split("/", 1)
            n = float(num)
            d = float(den)
            if d == 0:
                return None
            return n / d
        return float(value)
    except Exception:
        return None


def get_video_stream_info(file_path: str) -> dict:
    """
    Returns video stream metadata:
      codec, bitrate (bits/s), width, height, fps, duration
    Bitrate falls back to file_size/duration estimate when stream bitrate is unavailable.
    """
    info = {"codec": None, "bitrate": None, "width": None, "height": None, "fps": None, "duration": None}
    try:
        cmd = [
            FFPROBE_CMD, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name,bit_rate,width,height,avg_frame_rate,r_frame_rate:format=duration,bit_rate",
            "-of", "json",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=PROGRESS_TIMEOUT)
        if result.returncode != 0 or not result.stdout.strip():
            return info

        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        stream = streams[0] if streams else {}
        fmt = data.get("format", {})
        codec_name = str(stream.get("codec_name", "")).strip()
        if codec_name:
            info["codec"] = codec_name
        duration_str = str(fmt.get("duration", "")).strip()
        if duration_str and duration_str.replace(".", "", 1).isdigit():
            duration = float(duration_str)
            if duration > 0:
                info["duration"] = duration

        # Resolution
        width = stream.get("width")
        height = stream.get("height")
        if isinstance(width, int) and width > 0:
            info["width"] = width
        if isinstance(height, int) and height > 0:
            info["height"] = height

        # FPS (prefer avg_frame_rate, fallback to r_frame_rate)
        fps = _parse_ffprobe_fraction(str(stream.get("avg_frame_rate", "")))
        if not fps:
            fps = _parse_ffprobe_fraction(str(stream.get("r_frame_rate", "")))
        if fps and fps > 0:
            info["fps"] = fps

        # Bitrate from stream if available
        bit_rate = stream.get("bit_rate")
        if isinstance(bit_rate, str) and bit_rate.isdigit():
            info["bitrate"] = int(bit_rate)
        elif isinstance(bit_rate, int) and bit_rate > 0:
            info["bitrate"] = bit_rate

        format_bit_rate = fmt.get("bit_rate")
        if info["bitrate"] is None:
            if isinstance(format_bit_rate, str) and format_bit_rate.isdigit():
                info["bitrate"] = int(format_bit_rate)
            elif isinstance(format_bit_rate, int) and format_bit_rate > 0:
                info["bitrate"] = format_bit_rate

        # Fallback bitrate: derive from file size/duration
        if info["bitrate"] is None:
            if isinstance(info["duration"], (int, float)) and info["duration"] > 0:
                size = os.path.getsize(file_path)
                info["bitrate"] = int((size * 8 / float(info["duration"])) * VIDEO_BITRATE_ESTIMATE_FACTOR)

    except subprocess.TimeoutExpired:
        _sp, _lp = _path_console_log(file_path)
        cprint(f"Timeout while probing file: {_sp}", "warning", log_body=f"Timeout while probing file: {_lp}")
    except Exception as e:
        cprint(f"Could not probe stream info: {e}", "warning")

    return info


def get_recommended_bitrate(width: int, height: int, fps: float) -> int:
    """
    Estimate an efficient bitrate for given resolution/FPS.
    Uses resolution tiers with FPS scaling to avoid overly aggressive cuts on near-FHD content.
    """
    pixels = width * height
    if pixels <= 854 * 480:
        base_30fps = 1_200_000
    elif pixels <= 1280 * 720:
        base_30fps = 3_000_000
    elif pixels <= 1920 * 1080:
        base_30fps = 8_000_000
    elif pixels <= 2560 * 1440:
        base_30fps = 14_000_000
    else:
        base_30fps = 22_000_000

    # Scale linearly from a 30fps baseline, with sane bounds for edge FPS values.
    fps_scale = max(0.75, min(2.0, fps / 30.0))
    estimated = int(base_30fps * fps_scale)
    return max(RECOMMENDED_BITRATE_MIN, min(RECOMMENDED_BITRATE_MAX, estimated))

def _signal_handler(sig: int, frame) -> None:
    """Handle Ctrl+C gracefully during batch processing."""
    global _USER_CANCELLED
    _USER_CANCELLED = True
    cprint("\n\n⏸️  Gracefully stopping after current file...\n   (Press Ctrl+C again to force quit)", "warning")
    # Restore default handler so second Ctrl+C will force quit
    signal.signal(signal.SIGINT, signal.SIG_DFL)

def _save_log(log_type: str, log_path: Optional[str] = None) -> Optional[str]:
    """Save collected log messages to file (.txt, .html or .json).
    Returns the path to the saved log file, or None if disabled.
    """
    if not log_type or log_type.lower() == "none":
        return None
    
    if not _LOG_MESSAGES:
        return None
    
    # Create logs directory
    log_dir = log_path or "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    if log_type.lower() == "json":
        log_file = os.path.join(log_dir, f"{__app_name__}_{timestamp}.json")
        payload = {
            "app": __app_name__,
            "version": __version__,
            "generated": datetime.now(UTC).isoformat(timespec="seconds"),
            "system_platform": SYSTEM_PLATFORM,
            "encoder": ACTIVE_ENCODER,
            "events": _LOG_EVENTS or [
                {"ts": datetime.now(UTC).isoformat(timespec="seconds"), "level": "info", "message": m}
                for m in _LOG_MESSAGES
            ],
        }
        with open(log_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    elif log_type.lower() == "html":
        log_file = os.path.join(log_dir, f"{__app_name__}_{timestamp}.html")
        timestamp_formatted = time.strftime("%Y-%m-%d %H:%M:%S")
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{__app_name__} Log - {timestamp}</title>
    <style>
        body {{ font-family: monospace; margin: 20px; background: #1e1e1e; color: #d4d4d4; }}
        .log {{ white-space: pre-wrap; word-wrap: break-word; }}
        .success {{ color: #4ec9b0; }}
        .error {{ color: #f48771; }}
        .warning {{ color: #dcdcaa; }}
        .info {{ color: #569cd6; }}
    </style>
</head>
<body>
    <h2>{__app_name__} Conversion Log</h2>
    <p>Generated: {timestamp_formatted}</p>
    <div class="log">
{chr(10).join(_LOG_MESSAGES)}
    </div>
</body>
</html>
"""
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(html_content)
    else:
        # Default to .txt
        log_file = os.path.join(log_dir, f"{__app_name__}_{timestamp}.txt")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"{__app_name__} Conversion Log\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            f.write("\n".join(_LOG_MESSAGES))
    
    cprint(f"Log saved to: {log_file}", "success")
    return log_file

# ============================================================================ #
#                               FUNCTION: cprint                               #
# ============================================================================ #
def cprint(
    message: str,
    type: str = "",
    style: str = "bold green",
    *,
    log_body: Optional[str] = None,
    log_only: bool = False,
    **kwargs,
) -> None:
    timestamp = time.strftime('%H:%M:%S')
    prefix = ""
    style  = ""
    type   = type.lower()
    markup_enabled = kwargs.pop("markup", False)

    if type == "error":
        style = "red"
        prefix = "❌"
    elif type == "warning":
        style = "yellow"
        prefix = "⚠️"
    elif type == "info":
        style = "blue"
        prefix = "ℹ️"
    elif type == "success":
        style = "green"
        prefix = "✅"

    log_line_body = message if log_body is None else log_body
    console_msg = f"[{timestamp}] {prefix}  {message}"
    log_msg = f"[{timestamp}] {prefix}  {log_line_body}"

    # Disable styling if _NO_COLOR is set; respect suppression for console output only
    if not _SUPPRESS_OUTPUT and not log_only:
        if _NO_COLOR:
            console.print(console_msg, markup=markup_enabled, **kwargs)
        else:
            console.print(console_msg, style=style, markup=markup_enabled, **kwargs)

    # Log the message (with prefix for file logging) and structured event
    _LOG_MESSAGES.append(log_msg)
    try:
        _LOG_EVENTS.append({
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "level": type or "info",
            "message": log_msg,
        })
    except Exception:
        pass

# ============================================================================ #
#                            FUNCTION: safe_input                              #
# ============================================================================ #
def safe_input(prompt: str, message: Optional[str] = None) -> str:
    """
    Input function that pauses progress bar if active and ensures terminal is ready for input.
    Optionally prints a message after the progress display is stopped.
    """
    global _PROGRESS_CONTEXT, _SUPPRESS_OUTPUT, console
    
    # Stop progress bar if active and ensure it's properly stopped
    if _PROGRESS_CONTEXT:
        try:
            _PROGRESS_CONTEXT.stop()
            # Give it a moment to fully stop and restore terminal
            import time
            time.sleep(0.2)
            # Ensure console is ready for input
            try:
                console.show_cursor()
            except Exception:
                pass
        except Exception:
            pass
    
    # Temporarily disable output suppression to show prompt
    old_suppress = _SUPPRESS_OUTPUT
    _SUPPRESS_OUTPUT = False
    
    # Ensure we're on a new line and flush all output
    try:
        import sys
        # Print newline first to ensure we're on a fresh line
        sys.stdout.write("\n")
        sys.stdout.flush()
        sys.stderr.flush()
        # Ensure stdin is in the right mode
        if hasattr(sys.stdin, 'fileno'):
            try:
                import importlib
                import importlib.util as importlib_util
                # Dynamically check for the POSIX-only `termios` module to appease type checkers
                if importlib_util.find_spec("termios") is not None:
                    termios = importlib.import_module("termios")
                    fd = sys.stdin.fileno()
                    tcget = getattr(termios, "tcgetattr", None)
                    tcset = getattr(termios, "tcsetattr", None)
                    tcsadrain = getattr(termios, "TCSADRAIN", None)
                    if callable(tcget) and callable(tcset) and tcsadrain is not None:
                        old_settings = tcget(fd)
                        tcset(fd, tcsadrain, old_settings)
            except (ImportError, OSError, AttributeError):
                # Not a TTY or Windows - that's okay
                pass
    except Exception:
        pass
    
    try:
        if message:
            console.print(message)
        # Use Rich console.input() which handles terminal state better
        # But fallback to standard input() if that fails
        try:
            result = console.input(prompt)
        except (AttributeError, Exception):
            # Fallback to standard input
            result = input(prompt)
    except (EOFError, KeyboardInterrupt):
        # Handle Ctrl+C or EOF gracefully
        result = ""
    finally:
        # Restore output suppression state
        _SUPPRESS_OUTPUT = old_suppress
        
        # Restart progress bar if it was active
        if _PROGRESS_CONTEXT:
            try:
                _PROGRESS_CONTEXT.start()
            except Exception:
                pass
    
    return result

# ============================================================================ #
#                      FUNCTION: get_input_bitrate                             #
# ============================================================================ #
def get_input_bitrate(file_path: str) -> Optional[int]:
    """
    Returns the bitrate of the video stream in bits/s.
    Falls back to calculating from file size and duration if not available.
    """
    info = get_video_stream_info(file_path)
    bitrate = info.get("bitrate")
    return int(bitrate) if isinstance(bitrate, int) and bitrate > 0 else None


def get_audio_channels(file_path: str) -> Optional[int]:
    """Returns the number of channels in the first audio stream, or None if unavailable."""
    try:
        cmd = [
            FFPROBE_CMD, "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=channels",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=PROGRESS_TIMEOUT)
        val = result.stdout.strip()
        if val.isdigit():
            return int(val)
    except Exception:
        pass
    return None


# ============================================================================ #
#                       FUNCTION: check_encoder_support                        #
# ============================================================================ #
def check_encoder_support(encoder_name: str) -> bool:
    """
    Checks if a specific FFmpeg encoder is usable (drivers installed).
    Uses 720p test to satisfy RDNA3 and newer NVENC requirements.
    """
    global FFMPEG_CMD

    try:
        # Some hardware encoders require additional options to exercise the
        # encoder (for example VAAPI needs a device and hwupload). Build a
        # slightly different test command depending on encoder type.
        duration = "0.5"
        if "vaapi" in encoder_name:
            # VAAPI typically needs the vaapi device and a hwupload stage
            vaapi_dev = os.getenv("AV1_VAAPI_DEVICE", "/dev/dri/renderD128")
            cmd = [
                FFMPEG_CMD, "-v", "quiet", "-vaapi_device", vaapi_dev,
                "-f", "lavfi", "-i", f"testsrc=size=1280x720:rate=30:duration={duration}",
                "-vf", "format=nv12,hwupload", "-c:v", encoder_name, "-f", "null", "-"
            ]

            try:
                proc = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=ENCODER_TEST_TIMEOUT)
                if proc.returncode == 0:
                    return True

                # Inspect output for libva ABI / symbol resolution failures
                stderr = (proc.stderr or "") + (proc.stdout or "")
                if any(s in stderr for s in ("failed to resolve symbol", "vaMapBuffer2", "libva.so.2", "_libva_so_2_tramp_resolve")):
                    # Check if user wants automatic fallback (default: auto-detect for hardware encoding)
                    fallback_env = os.getenv("AV1_FFMPEG_FALLBACK", "auto")
                    allow_fallback = _env_bool(fallback_env) if fallback_env != "auto" else None
                    ignore_warning = _env_bool(os.getenv("AV1_IGNORE_LIBVA_WARNING", "true"))  # Default: try anyway
                    
                    # Auto-fallback: try system ffmpeg for hardware encoding if PATH ffmpeg has libva issues
                    should_try_fallback = (allow_fallback is True) or (fallback_env == "auto" and encoder_name.endswith("_vaapi"))
                    
                    if should_try_fallback:
                        fallback = "/usr/bin/ffmpeg"
                        if os.path.exists(fallback) and os.path.isfile(fallback) and fallback != FFMPEG_CMD:
                            fallback_cmd = [
                                fallback, "-v", "quiet", "-vaapi_device", vaapi_dev,
                                "-f", "lavfi", "-i", f"testsrc=size=1280x720:rate=30:duration={duration}",
                                "-vf", "format=nv12,hwupload", "-c:v", encoder_name, "-f", "null", "-"
                            ]
                            try:
                                proc2 = subprocess.run(fallback_cmd, check=False, capture_output=True, text=True, timeout=ENCODER_TEST_TIMEOUT)
                                if proc2.returncode == 0:
                                    # Switch global ffmpeg to the working distro binary for hardware encoding
                                    FFMPEG_CMD = fallback
                                    cprint("Detected libva ABI mismatch in PATH ffmpeg; using system ffmpeg for hardware encoding.", "warning")
                                    cprint("(PATH ffmpeg will still be used for CPU encoding if needed)", "info")
                                    return True
                            except Exception:
                                pass
                    
                    # If ignoring warning, try using the encoder anyway (user wants PATH ffmpeg)
                    if ignore_warning:
                        cprint("Detected libva ABI mismatch warning, but attempting to use hardware encoder with PATH ffmpeg.", "warning")
                        cprint("If encoding fails, set AV1_FFMPEG_FALLBACK=auto to automatically use system ffmpeg for hardware encoding.", "info")
                        return True  # Try it anyway - might work despite the warning
                    else:
                        cprint("Detected libva ABI mismatch in ffmpeg. Hardware encoding may not work.", "warning")
                        cprint("Set AV1_FFMPEG_FALLBACK=auto to automatically use system ffmpeg for hardware encoding.", "info")

                return False
            except Exception:
                return False
        else:
            # Default test (works for NVENC/AMF/CPU encoders)
            cmd = [
                FFMPEG_CMD, "-v", "quiet", "-f", "lavfi",
                "-i", f"testsrc=size=1280x720:rate=30:duration={duration}",
                "-c:v", encoder_name, "-f", "null", "-"
            ]

            try:
                return subprocess.run(cmd, check=False, timeout=ENCODER_TEST_TIMEOUT).returncode == 0
            except Exception:
                return False
    except Exception:
        return False

# ============================================================================ #
#                            FUNCTION: check_ffmpeg                            #
# ============================================================================ #
def check_ffmpeg() -> None:
    global ACTIVE_ENCODER, FFMPEG_CMD, FFPROBE_CMD
    # Validate ffmpeg path or fallback to PATH
    resolved_ffmpeg = _resolve_executable_path(FFMPEG_CMD, "ffmpeg")
    if not resolved_ffmpeg:
        cprint("ffmpeg is not found.", "error")
        raise typer.Exit(code=1)
    FFMPEG_CMD = resolved_ffmpeg
    check_ffprobe()
    
    cprint("Detecting Best Available Encoder...", "info")
    
    # --- WINDOWS PRIORITY ---
    if SYSTEM_PLATFORM == "windows":
        # PRIORITY 1: AV1 HARDWARE (RTX 40-series / RX 7000-series)
        if check_encoder_support("av1_nvenc"):
            ACTIVE_ENCODER = {"encoder": "av1_nvenc", "codec": "av1", "hw_type": "nvidia"}
            cprint("Hardware Found: NVIDIA AV1 (`av1_nvenc`).", "success")
            return
            
        if check_encoder_support("av1_amf"):
            ACTIVE_ENCODER = {"encoder": "av1_amf", "codec": "av1", "hw_type": "amd"}
            cprint("Hardware Found: AMD AV1 (`av1_amf`).", "success")
            return

        # PRIORITY 2: HEVC HARDWARE (GTX 900+ / RX 5000+)
        if check_encoder_support("hevc_nvenc"):
            ACTIVE_ENCODER = {"encoder": "hevc_nvenc", "codec": "hevc", "hw_type": "nvidia"}
            cprint("Hardware Found: NVIDIA HEVC (`hevc_nvenc`).", "success")
            return

        if check_encoder_support("hevc_amf"):
            ACTIVE_ENCODER = {"encoder": "hevc_amf", "codec": "hevc", "hw_type": "amd"}
            cprint("Hardware Found: AMD HEVC (`hevc_amf`).", "success")
            return
    
    # --- LINUX/MAC PRIORITY (VAAPI for Intel/AMD GPUs on Linux) ---
    elif SYSTEM_PLATFORM == "linux":
        # PRIORITY 1: AV1 VAAPI (Intel/AMD GPUs on Linux)
        if check_encoder_support("av1_vaapi"):
            ACTIVE_ENCODER = {"encoder": "av1_vaapi", "codec": "av1", "hw_type": "vaapi"}
            cprint("Hardware Found: VAAPI AV1 (`av1_vaapi`).", "success")
            return
        
        # PRIORITY 2: NVIDIA NVENC (Linux with NVIDIA GPU)
        if check_encoder_support("av1_nvenc"):
            ACTIVE_ENCODER = {"encoder": "av1_nvenc", "codec": "av1", "hw_type": "nvidia"}
            cprint("Hardware Found: NVIDIA AV1 (`av1_nvenc`).", "success")
            return
        
        # PRIORITY 3: HEVC VAAPI
        if check_encoder_support("hevc_vaapi"):
            ACTIVE_ENCODER = {"encoder": "hevc_vaapi", "codec": "hevc", "hw_type": "vaapi"}
            cprint("Hardware Found: VAAPI HEVC (`hevc_vaapi`).", "success")
            return
        
        # PRIORITY 4: HEVC NVENC (Linux with NVIDIA GPU)
        if check_encoder_support("hevc_nvenc"):
            ACTIVE_ENCODER = {"encoder": "hevc_nvenc", "codec": "hevc", "hw_type": "nvidia"}
            cprint("Hardware Found: NVIDIA HEVC (`hevc_nvenc`).", "success")
            return

    # --- PRIORITY 3: CPU FALLBACK (ALL PLATFORMS) ---
    ACTIVE_ENCODER = {"encoder": "libsvtav1", "codec": "av1", "hw_type": "cpu"}
    cprint("No Hardware Encoder detected. Using CPU (`libsvtav1`).", "warning")


def check_ffprobe() -> None:
    """Validate ffprobe path or fallback to PATH."""
    global FFPROBE_CMD
    resolved_ffprobe = _resolve_executable_path(FFPROBE_CMD, "ffprobe")
    if not resolved_ffprobe:
        cprint("ffprobe is not found.", "error")
        raise typer.Exit(code=1)
    FFPROBE_CMD = resolved_ffprobe

# ============================================================================ #
#                          FUNCTION: needs_transcoding                         #
# ============================================================================ #
def needs_transcoding(file_path: str) -> bool:
    """
    Determines if a video file needs transcoding based on current codec.
    Returns True if transcoding is needed, False otherwise.
    Also detects corrupt/invalid files and reports them.
    """
    return inspect_transcoding_need(file_path) == "needs"

# ============================================================================ #
#                     FUNCTION: inspect_transcoding_need                        #
# ============================================================================ #
def inspect_transcoding_need(file_path: str) -> str:
    """
    Inspect whether a file should be transcoded.
    Returns one of: needs, already-av1, already-target, invalid.
    """
    try:
        cmd = [FFPROBE_CMD, "-v", "error", "-print_format", "json", "-show_streams", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=PROGRESS_TIMEOUT)

        if result.returncode != 0:
            stderr_lower = result.stderr.lower() if result.stderr else ""
            corruption_keywords = [
                "corrupt", "invalid", "moov atom not found", "could not find codec parameters",
                "error while decoding", "invalid data found", "bitstream not supported",
                "error reading header", "end of file", "truncated"
            ]

            is_corrupt = any(keyword in stderr_lower for keyword in corruption_keywords)

            if is_corrupt:
                _sp, _lp = _path_console_log(file_path)
                cprint(f"❌ Corrupt file detected: {_sp}", "error", log_body=f"❌ Corrupt file detected: {_lp}")
                if result.stderr:
                    error_msg = result.stderr.strip()[:200]
                    cprint(f"   Error: {error_msg}", "error")
            else:
                _sp, _lp = _path_console_log(file_path)
                cprint(
                    f"⚠️  Could not probe {_sp} - may be invalid or unsupported",
                    "warning",
                    log_body=f"⚠️  Could not probe {_lp} - may be invalid or unsupported",
                )
            return "invalid"

        data = json.loads(result.stdout)
        target_codec = ACTIVE_ENCODER["codec"]
        video_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'video']
        if not video_streams:
            _sp, _lp = _path_console_log(file_path)
            cprint(
                f"❌ Corrupt or invalid file: {_sp} (no video stream found)",
                "error",
                log_body=f"❌ Corrupt or invalid file: {_lp} (no video stream found)",
            )
            return "invalid"

        for stream in video_streams:
            current_codec = stream.get('codec_name')
            if target_codec == "av1" and current_codec == "av1":
                return "already-av1"
            if target_codec == "hevc" and current_codec in ['hevc', 'h265', 'av1']:
                return "already-target"
            return "needs"

        return "needs"
    except subprocess.TimeoutExpired:
        _sp, _lp = _path_console_log(file_path)
        cprint(
            f"⏱️  Timeout while probing {_sp} - file may be very large or corrupt",
            "warning",
            log_body=f"⏱️  Timeout while probing {_lp} - file may be very large or corrupt",
        )
        return "invalid"
    except json.JSONDecodeError:
        _sp, _lp = _path_console_log(file_path)
        cprint(
            f"❌ Corrupt file detected: {_sp} (invalid metadata)",
            "error",
            log_body=f"❌ Corrupt file detected: {_lp} (invalid metadata)",
        )
        return "invalid"
    except Exception as e:
        error_str = str(e).lower()
        if any(keyword in error_str for keyword in ["corrupt", "invalid", "truncated", "error reading"]):
            _sp, _lp = _path_console_log(file_path)
            cprint(f"❌ Corrupt file detected: {_sp}", "error", log_body=f"❌ Corrupt file detected: {_lp}")
            cprint(f"   Error: {str(e)[:200]}", "error")
        else:
            _sp, _lp = _path_console_log(file_path)
            cprint(f"⚠️  Error checking file {_sp}: {e}", "warning", log_body=f"⚠️  Error checking file {_lp}: {e}")
        return "invalid"

# ============================================================================ #
#                    FUNCTION: maybe_reencode_existing_av1                      #
# ============================================================================ #
def maybe_reencode_existing_av1(file_path: str, auto_reencode: bool = False) -> bool:
    """
    Ask whether an existing AV1 file should be re-encoded.
    Returns True if conversion should continue.
    """
    global _AUTO_REENCODE_AV1

    if auto_reencode or _AUTO_REENCODE_AV1:
        return True

    if _NO_PROMPT:
        _sp, _lp = _path_console_log(file_path)
        cprint(
            f"⏭️  Skipping: {_sp} (already AV1; use --reencode-av1 to bypass the prompt)",
            "info",
            log_body=f"⏭️  Skipping: {_lp} (already AV1; use --reencode-av1 to bypass the prompt)",
        )
        return False

    resp = safe_input(
        PROMPT_YES_NO_ALL,
        message=(
            "File is already AV1.\n"
            "Re-encode anyway?\n"
            f"{_display_path(file_path, full_path=True, fallback_label='input file')}"
        ),
    ).strip().lower()
    if resp in ("a", "all"):
        _AUTO_REENCODE_AV1 = True
        return True
    return resp in ("y", "yes")

# ============================================================================ #
#                        FUNCTION: maybe_delete_original                       #
# ============================================================================ #
def maybe_delete_original(original_path: str, auto_delete: bool = False) -> bool:
    """
    Prompts to delete the original file or deletes automatically.
    Returns True if user wants to auto-delete remaining files, False otherwise.
    """
    try:
        if auto_delete:
            os.remove(original_path)
            _sp, _lp = _path_console_log(original_path, fallback_label="original file")
            cprint(
                f"Deleted original: {_sp}",
                "success",
                log_body=f"Deleted original: {_lp}",
            )
            return True
        # Suppress interactive prompt when _NO_PROMPT is enabled
        if _NO_PROMPT:
            return False
        # Print question and path explicitly so [Y/n/a] is always visible (Rich may not
        # display multi-line prompts correctly on all terminals)
        prompt_target = _display_path(original_path, full_path=True, fallback_label="original file")
        resp = safe_input(
            PROMPT_YES_NO_ALL,
            message=f"Delete original file?\n{prompt_target}",
        ).strip().lower()
        if resp in ("y", "yes"):
            os.remove(original_path)
            cprint("Original deleted.", "success")
            return False
        elif resp in ("a", "all"):
            os.remove(original_path)
            cprint("Original deleted.", "success")
            return True
    except PermissionError:
        cprint(f"Permission denied: Cannot delete {_display_path(original_path, full_path=True, fallback_label='original file')}", "error")
    except Exception as e:
        cprint(f"Could not delete {_display_path(original_path, full_path=True, fallback_label='original file')}: {e}", "warning")
    return False

# ============================================================================ #
#                        FUNCTION: check_disk_space                            #
# ============================================================================ #
def resolve_output_dir(output_dir: Optional[str], input_path: Optional[str] = None) -> str:
    """
    Normalizes the destination directory for outputs and temp files.
    Empty dirnames can occur when wildcard matches are relative paths.
    """
    if output_dir:
        return output_dir
    if input_path:
        return os.path.dirname(input_path) or os.getcwd()
    return os.getcwd()


def resolve_original_output_path(input_path: str, output_path: str) -> Optional[str]:
    """Return the final original-name target when it is safe to rename in place."""
    input_dir = os.path.abspath(os.path.dirname(input_path) or os.getcwd())
    output_dir = os.path.abspath(os.path.dirname(output_path) or os.getcwd())
    if input_dir != output_dir:
        return None
    original_name_path = os.path.join(output_dir, os.path.basename(input_path))
    if os.path.abspath(output_path) == os.path.abspath(original_name_path):
        return None
    return original_name_path


def maybe_rename_output_to_original(output_path: str, original_name_path: str) -> None:
    """
    Optionally rename encoded output to the source basename/extension (in-place workflow).
    Interactive: y = this file, n = keep -CODEC.mkv name, A/a/all = yes to all such prompts this run.
    """
    global _AUTO_RENAME_TO_ORIGINAL

    def _do_rename() -> None:
        os.replace(output_path, original_name_path)
        _sp, _lp = _path_console_log(original_name_path, fallback_label="original name")
        cprint(f"Renamed to: {_sp}", "success", log_body=f"Renamed to: {_lp}")

    if _AUTO_RENAME_TO_ORIGINAL:
        try:
            _do_rename()
        except OSError as e:
            cprint(f"Could not rename to original name: {e}", "warning")
        return

    if _NO_PROMPT:
        try:
            _do_rename()
        except OSError as e:
            cprint(f"Could not rename to original name: {e}", "warning")
        return

    prompt_target = _display_path(original_name_path, full_path=True, fallback_label="target path")
    resp = safe_input(
        PROMPT_YES_NO_ALL,
        message=(
            "Rename output to original filename (restore extension in place)?\n"
            f"{prompt_target}"
        ),
    ).strip().lower()
    try:
        if resp in ("a", "all"):
            _AUTO_RENAME_TO_ORIGINAL = True
            _do_rename()
        elif resp in ("y", "yes"):
            _do_rename()
    except OSError as e:
        cprint(f"Could not rename to original name: {e}", "warning")


def _build_output_paths(input_path: str, output_dir: Optional[str], codec: str) -> tuple[str, str, str]:
    """Resolve output directory and the final/temp output paths for a conversion."""
    filename = os.path.basename(input_path)
    resolved_output_dir = resolve_output_dir(output_dir, input_path) or os.getcwd()
    if resolved_output_dir != (os.path.dirname(input_path) or os.getcwd()):
        os.makedirs(resolved_output_dir, exist_ok=True)

    output_name = os.path.splitext(filename)[0] + f"-{codec.upper()}.mkv"
    output_path = os.path.join(resolved_output_dir, output_name)
    temp_output = f"{output_path}.temp.mkv"
    return resolved_output_dir, output_path, temp_output


def _finalize_output_file(input_path: str, output_path: str, keep_mkv: bool, delete_original: bool) -> bool:
    """Handle original deletion and optional rename back to the original filename."""
    auto_delete_flag = maybe_delete_original(input_path, auto_delete=delete_original)
    if auto_delete_flag:
        delete_original = True

    original_deleted = not os.path.exists(input_path)
    original_name_path = resolve_original_output_path(input_path, output_path)
    if original_deleted and original_name_path and not keep_mkv:
        maybe_rename_output_to_original(output_path, original_name_path)
    return delete_original


def check_disk_space(file_path: str, output_dir: str) -> bool:
    """
    Verifies sufficient disk space is available for conversion.
    Returns True if enough space, False otherwise.
    """
    try:
        file_size = os.path.getsize(file_path)
        required_space = int(file_size * DISK_SPACE_SAFETY_MARGIN)
        
        output_dir = resolve_output_dir(output_dir)
        
        stat = shutil.disk_usage(output_dir)
        if stat.free < required_space:
            cprint(f"Insufficient disk space. Need {required_space / (1024**3):.2f} GB, have {stat.free / (1024**3):.2f} GB", "error")
            return False
        return True
    except Exception as e:
        cprint(f"Could not check disk space: {e}", "warning")
        return True  # Proceed anyway if we can't check

# ============================================================================ #
#                         FUNCTION: validate_video_file                        #
# ============================================================================ #
def validate_video_file(file_path: str, *, quiet: bool = False) -> bool:
    """
    Validates that a file is a supported video file.
    Returns True if valid, False otherwise.
    If quiet, do not log warnings (used for batch listing).
    """
    if not os.path.isfile(file_path):
        return False
        
    if not file_path.lower().endswith(SUPPORTED_EXTENSIONS):
        return False
    
    # Check minimum file size
    try:
        sz = os.path.getsize(file_path)
        if sz < MIN_FILE_SIZE_BYTES:
            if not quiet:
                _sp, _lp = _path_console_log(file_path)
                sz_h = _format_size(float(sz))
                min_h = _format_size(float(MIN_FILE_SIZE_BYTES))
                detail = f"{sz_h} ({sz} bytes); minimum {min_h} ({MIN_FILE_SIZE_BYTES} bytes)"
                cprint(
                    f"File too small: {_sp} ({detail})",
                    "warning",
                    log_body=f"File too small: {_lp} ({detail})",
                )
                try:
                    _LOG_EVENTS.append({
                        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                        "level": "warning",
                        "message": "skip_too_small",
                        "data": {
                            "file": _display_path(file_path, full_path=True, fallback_label="hidden"),
                            "size_bytes": sz,
                            "min_size_bytes": MIN_FILE_SIZE_BYTES,
                        },
                    })
                except Exception:
                    pass
            return False
    except OSError:
        return False
        
    return True


def _collect_directory_video_files(input_path: str, recursive: bool) -> list[str]:
    """Collect supported video files from a directory."""
    video_files = []
    if recursive:
        for root, dirs, files in os.walk(input_path):
            for filename in files:
                if filename.lower().endswith(SUPPORTED_EXTENSIONS):
                    video_files.append(os.path.join(root, filename))
    else:
        for filename in os.listdir(input_path):
            file_path = os.path.join(input_path, filename)
            if os.path.isfile(file_path) and filename.lower().endswith(SUPPORTED_EXTENSIONS):
                video_files.append(file_path)
    video_files.sort()
    return video_files


def _expand_cli_input_paths(input_paths: list[str]) -> list[str]:
    """Expand wildcard CLI inputs while preserving unmatched paths for diagnostics."""
    expanded_paths = []
    for input_path in input_paths:
        if "*" in input_path or "?" in input_path:
            matches = glob.glob(input_path)
            if matches:
                expanded_paths.extend(matches)
            else:
                expanded_paths.append(input_path)
        else:
            expanded_paths.append(input_path)
    return expanded_paths


def _resolve_video_input_files(input_paths: list[str], recursive: bool = False) -> list[str]:
    """Resolve files, directories, and wildcard patterns into concrete video files."""
    resolved_files = []
    for input_path in _expand_cli_input_paths(input_paths):
        if os.path.isfile(input_path):
            if input_path.lower().endswith(SUPPORTED_EXTENSIONS):
                resolved_files.append(input_path)
            else:
                _sp, _lp = _path_console_log(input_path)
                cprint(f"Skipping unsupported file: {_sp}", "warning", log_body=f"Skipping unsupported file: {_lp}")
        elif os.path.isdir(input_path):
            resolved_files.extend(_collect_directory_video_files(input_path, recursive))
        else:
            _sp, _lp = _path_console_log(input_path)
            cprint(f"Skipping invalid path: {_sp}", "warning", log_body=f"Skipping invalid path: {_lp}")

    return sorted(dict.fromkeys(resolved_files))


def _collect_directory_temp_files(input_path: str, recursive: bool) -> list[str]:
    """Collect temporary AV1 output artifacts from a directory."""
    temp_files = []
    if recursive:
        for root, dirs, files in os.walk(input_path):
            for filename in files:
                if filename.lower().endswith(TEMP_OUTPUT_SUFFIX):
                    temp_files.append(os.path.join(root, filename))
    else:
        for filename in os.listdir(input_path):
            file_path = os.path.join(input_path, filename)
            if os.path.isfile(file_path) and filename.lower().endswith(TEMP_OUTPUT_SUFFIX):
                temp_files.append(file_path)
    temp_files.sort()
    return temp_files


def _resolve_cleanup_targets(input_paths: list[str], recursive: bool = False) -> list[str]:
    """Resolve cleanup inputs into concrete stale temp-output files."""
    resolved_files = []
    for input_path in _expand_cli_input_paths(input_paths):
        if os.path.isfile(input_path):
            if input_path.lower().endswith(TEMP_OUTPUT_SUFFIX):
                resolved_files.append(input_path)
        elif os.path.isdir(input_path):
            resolved_files.extend(_collect_directory_temp_files(input_path, recursive))
        else:
            _sp, _lp = _path_console_log(input_path)
            cprint(f"Skipping invalid path: {_sp}", "warning", log_body=f"Skipping invalid path: {_lp}")

    return sorted(dict.fromkeys(resolved_files))


def _remove_cleanup_targets(temp_files: list[str]) -> tuple[int, int]:
    """Delete resolved cleanup files. Returns (removed_count, failed_count)."""
    removed_count = 0
    failed_count = 0

    for temp_file in temp_files:
        if not temp_file.lower().endswith(TEMP_OUTPUT_SUFFIX):
            continue
        try:
            os.remove(temp_file)
            removed_count += 1
            _sp, _lp = _path_console_log(temp_file)
            cprint(f"Removed temp file: {_sp}", "success", log_body=f"Removed temp file: {_lp}")
        except OSError as e:
            failed_count += 1
            _sp, _lp = _path_console_log(temp_file)
            cprint(f"Could not remove {_sp}: {e}", "warning", log_body=f"Could not remove {_lp}: {e}")

    return removed_count, failed_count


def _resolve_batch_base_path(video_files: list[str]) -> str:
    """Choose a stable base path for batch progress display."""
    try:
        if len(video_files) > 1:
            return os.path.commonpath(video_files)
        return os.path.dirname(video_files[0]) or os.getcwd()
    except (ValueError, IndexError):
        return os.getcwd()


def probe_inputs(input_paths: list[str], recursive: bool = False) -> None:
    """Probe input files and print media metadata without converting."""
    probe_targets = _resolve_video_input_files(input_paths, recursive=recursive)
    if not probe_targets:
        cprint("❌ No video files found to probe.", "error")
        raise typer.Exit(code=1)

    cprint(f"🔎 Probing {len(probe_targets)} file(s)...", "info")
    for file_path in probe_targets:
        if not validate_video_file(file_path):
            _sp, _lp = _path_console_log(file_path)
            cprint(f"Skipping invalid video file: {_sp}", "warning", log_body=f"Skipping invalid video file: {_lp}")
            continue
        stream_info = get_video_stream_info(file_path)
        width = stream_info.get("width")
        height = stream_info.get("height")
        resolution = (
            f"{width}x{height}"
            if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0
            else "unknown"
        )
        file_size = None
        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            pass

        _sp, _lp = _path_console_log(file_path)
        cprint(f"Probe: {_sp}", "info", log_body=f"Probe: {_lp}")
        cprint(f"   Codec:     {stream_info.get('codec') or 'unknown'}", "info")
        cprint(f"   Resolution: {resolution}", "info")
        cprint(f"   FPS:       {_format_fps_display(stream_info.get('fps'))}", "info")
        cprint(f"   Bitrate:   {_format_bitrate_display(stream_info.get('bitrate'))}", "info")
        cprint(f"   Duration:  {_format_duration(stream_info.get('duration'))}", "info")
        cprint(f"   Filesize:  {_format_size(float(file_size)) if file_size else 'unknown'}", "info")


def _run_list_command(
    input_paths: Optional[list[str]],
    recursive: bool,
    no_color: bool,
    hide_filenames: bool,
    ffprobe_path: Optional[str],
) -> None:
    """
    List supported video files under the given path(s) with video codec and on-disk size.
    Defaults to the current working directory when no paths are given.
    """
    global _NO_COLOR, _HIDE_FILENAMES, console, FFPROBE_CMD

    env_no_color = os.getenv("AV1_NO_COLOR")
    if env_no_color and _env_bool(env_no_color):
        no_color = True
    env_hide = os.getenv("AV1_HIDE_FILENAMES")
    if env_hide and _env_bool(env_hide):
        hide_filenames = True

    if ffprobe_path:
        FFPROBE_CMD = ffprobe_path
    _NO_COLOR = no_color
    _HIDE_FILENAMES = hide_filenames
    if no_color:
        console = Console(no_color=True, force_terminal=True)

    if not input_paths:
        input_paths = [os.getcwd()]

    check_ffprobe()

    video_files = _resolve_video_input_files(input_paths, recursive=recursive)
    if not video_files:
        cprint("❌ No video files found.", "error")
        raise typer.Exit(code=1)

    _confirm_root_like_input_paths(list(input_paths), intent="list", recursive=recursive)

    base_path = _resolve_batch_base_path(video_files)
    table = Table(show_header=True, header_style="bold", show_lines=False)
    table.add_column("File", overflow="fold", no_wrap=False)
    table.add_column("Codec", overflow="fold")
    table.add_column("Size", justify="right", overflow="fold")

    total_bytes = 0
    for file_path in video_files:
        try:
            sz = os.path.getsize(file_path)
        except OSError:
            sz = 0
        total_bytes += sz
        size_str = _format_size(float(sz))
        display = _display_path(file_path, base_path=base_path, fallback_label="file")
        if not validate_video_file(file_path, quiet=True):
            codec_str = "—"
        else:
            info = get_video_stream_info(file_path)
            codec_str = str(info.get("codec") or "unknown")
        table.add_row(display, codec_str, size_str)

    mode = "recursive" if recursive else "non-recursive"
    cprint(f"📋 Video files ({len(video_files)}, {mode})", "info")
    console.print(table)
    cprint(
        f"Total: {_format_size(float(total_bytes))} ({total_bytes} bytes) — {len(video_files)} file(s)",
        "info",
    )


def _terminate_ffmpeg_process(process: subprocess.Popen, command: list[str], reason: str) -> None:
    """Stop a hung ffmpeg process without leaving it running in the background."""
    try:
        process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
            process.wait(timeout=5)
        except Exception:
            pass
    except Exception:
        pass
    raise subprocess.TimeoutExpired(command, FFMPEG_STALL_TIMEOUT, output=reason)


def _iter_ffmpeg_output_with_stall_timeout(
    process: subprocess.Popen,
    command: list[str],
    stall_timeout: int,
):
    """Yield ffmpeg output lines while aborting if progress stalls."""
    if process.stdout is None:
        return

    lines = queue.Queue()

    def _reader() -> None:
        try:
            for stdout_line in process.stdout:
                lines.put(stdout_line)
        finally:
            lines.put(None)

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    last_output = time.monotonic()

    while True:
        try:
            line = lines.get(timeout=0.5)
        except queue.Empty:
            if process.poll() is not None:
                break
            if stall_timeout > 0 and (time.monotonic() - last_output) > stall_timeout:
                _terminate_ffmpeg_process(process, command, "ffmpeg produced no output before stall timeout")
            continue

        if line is None:
            break
        last_output = time.monotonic()
        yield line


@dataclass(frozen=True)
class ConversionRetryOptions:
    """Options that must stay identical when a conversion retries with another encoder."""
    input_path: str
    output_dir: Optional[str]
    bitrate: Optional[str]
    delete_original: bool
    overwrite: bool
    dry_run: bool
    keep_mkv: bool
    show_progress: bool
    batch_index: Optional[int]
    batch_total: Optional[int]
    progress_label: Optional[str]
    progress_callback: Optional[Callable[[Optional[float], str, str], None]]
    cpu_threads: Optional[int]
    prompt_av1: bool
    reencode_av1: bool
    max_output_bytes: Optional[int]
    min_shrink_percent: Optional[float]
    max_video_width: Optional[int]


def _retry_convert_single_file(options: ConversionRetryOptions) -> Tuple[bool, int, str, str]:
    """Retry a conversion without dropping less-common options."""
    return convert_single_file(
        options.input_path,
        options.output_dir,
        options.bitrate,
        options.delete_original,
        options.overwrite,
        options.dry_run,
        options.keep_mkv,
        options.show_progress,
        batch_index=options.batch_index,
        batch_total=options.batch_total,
        progress_label=options.progress_label,
        progress_callback=options.progress_callback,
        cpu_threads=options.cpu_threads,
        prompt_av1=options.prompt_av1,
        reencode_av1=options.reencode_av1,
        max_output_bytes=options.max_output_bytes,
        min_shrink_percent=options.min_shrink_percent,
        max_video_width=options.max_video_width,
    )


def _parse_bitrate_to_bps(bitrate: str) -> int:
    """Parse bitrate strings such as 2500k, 2.5m, or raw bits per second."""
    normalized = str(bitrate).strip().lower()
    if normalized.endswith("m"):
        return int(float(normalized[:-1]) * 1_000_000)
    if normalized.endswith("k"):
        return int(float(normalized[:-1]) * 1_000)
    return int(normalized)


def _select_pixel_format(hw_type: str) -> str:
    """Return the pixel format expected by the active encoder type."""
    return "yuv420p" if hw_type == "cpu" else "nv12"


def _build_video_filter_chain(hw_type: str, max_video_width: int, pix_fmt: str) -> str:
    """Build the scaling/filter chain for the selected encoder family."""
    if hw_type == "vaapi":
        return f"scale='min({max_video_width},iw)':-2:force_original_aspect_ratio=decrease,format={pix_fmt},hwupload"
    if hw_type == "amd":
        return (
            f"scale='trunc(min({max_video_width},iw)/64)*64':'trunc(trunc(min({max_video_width},iw)/64)*64*ih/iw/16)*16',"
            f"format={pix_fmt}"
        )
    return f"scale='min({max_video_width},iw)':-2:force_original_aspect_ratio=decrease,format={pix_fmt}"


def _append_encoder_rate_control_args(
    command: list[str],
    *,
    hw_type: str,
    target_bitrate_int: int,
    effective_cpu_threads: int,
) -> None:
    """Append encoder-specific options without mixing hardware and CPU-only flags."""
    bitrate_args = [
        "-b:v", str(target_bitrate_int),
        "-maxrate", str(int(target_bitrate_int * BITRATE_MAXRATE_MULTIPLIER)),
        "-bufsize", str(int(target_bitrate_int * BITRATE_BUFSIZE_MULTIPLIER)),
    ]
    if hw_type == "nvidia":
        command.extend(["-preset", "p7", "-rc", "vbr"])
        command.extend(bitrate_args)
    elif hw_type == "amd":
        command.extend(["-usage", "0", "-quality", "70", "-profile:v", "1", "-rc", "1", "-align", "3"])
        command.extend(["-b:v", str(target_bitrate_int)])
    elif hw_type == "vaapi":
        command.extend(bitrate_args)
    else:
        command.extend(["-preset", "8", "-g", "240", "-svtav1-params", f"lp={effective_cpu_threads}"])
        command.extend(["-b:v", str(target_bitrate_int)])


def _build_audio_args(audio_channels: Optional[int], temp_output: str) -> list[str]:
    """Build audio encoding arguments, preserving the special 5.1(side) mapping."""
    if audio_channels == 6:
        return [
            "-af",
            "channelmap=map=FL-FL|FR-FR|FC-FC|LFE-LFE|SL-BL|SR-BR",
            "-c:a",
            "libopus",
            "-b:a",
            AUDIO_BITRATE,
            temp_output,
        ]
    return ["-c:a", "libopus", "-b:a", AUDIO_BITRATE, temp_output]


def _build_ffmpeg_command(
    *,
    ffmpeg_cmd: str,
    input_path: str,
    output_path: str,
    temp_output: str,
    encoder_name: str,
    hw_type: str,
    codec: str,
    target_bitrate_int: int,
    effective_cpu_threads: int,
    effective_max_width: int,
    audio_channels: Optional[int],
) -> tuple[list[str], str]:
    """Build the ffmpeg command and return it with the selected pixel format."""
    pix_fmt = _select_pixel_format(hw_type)
    command = [ffmpeg_cmd, "-y", "-hide_banner", "-progress", "pipe:1", "-nostats"]
    if hw_type == "vaapi":
        command.extend(["-vaapi_device", os.getenv("AV1_VAAPI_DEVICE", "/dev/dri/renderD128")])

    command.extend(["-i", input_path])
    command.extend(["-vf", _build_video_filter_chain(hw_type, effective_max_width, pix_fmt)])
    if output_path.lower().endswith((".mp4", ".m4v", ".mov")):
        command.extend(["-movflags", "+faststart"])

    command.extend(["-c:v", encoder_name])
    if output_path.lower().endswith((".mp4", ".m4v", ".mov")):
        command.extend(["-metadata", "major_brand=mp42", "-metadata", "compatible_brands=mp42av01iso2mp41"])
    if codec == "hevc":
        command.extend(["-tag:v", "hvc1"])

    _append_encoder_rate_control_args(
        command,
        hw_type=hw_type,
        target_bitrate_int=target_bitrate_int,
        effective_cpu_threads=effective_cpu_threads,
    )
    command.extend(_build_audio_args(audio_channels, temp_output))
    return command, pix_fmt


# ============================================================================ #
#                         FUNCTION: convert_single_file                        #
# ============================================================================ #
def convert_single_file(
    input_path: str,
    output_dir: Optional[str] = None,
    bitrate: Optional[str] = None,
    delete_original: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
    keep_mkv: bool = False,
    show_progress: bool = True,
    batch_index: Optional[int] = None,
    batch_total: Optional[int] = None,
    progress_label: Optional[str] = None,
    progress_callback: Optional[Callable[[Optional[float], str, str], None]] = None,
    cpu_threads: Optional[int] = None,
    prompt_av1: bool = False,
    reencode_av1: bool = False,
    *,
    max_output_bytes: Optional[int] = None,
    min_shrink_percent: Optional[float] = None,
    max_video_width: Optional[int] = None,
) -> Tuple[bool, int, str, str]:
    """
    Converts a single video file to the target codec.
    Returns a tuple: (auto_delete_flag, size_saved_bytes, bitrate_decision, media_info)
    - auto_delete_flag: True if user selected 'all' for auto-delete
    - size_saved_bytes: Bytes saved (positive) or added (negative), 0 if skipped/failed
    - bitrate_decision: Short human-readable bitrate strategy used for this file
    - media_info: Short media metadata string (resolution, length, fps)
    """
    global ACTIVE_ENCODER, FFMPEG_CMD, _AUTO_OVERWRITE_EXISTING
    display_name = _display_path(input_path)
    display_name_log = _display_path(input_path, full_path=True, fallback_label="hidden")
    progress_name = progress_label or display_name
    effective_cpu_threads = _resolve_cpu_threads(cpu_threads)
    effective_max_width = int(max_video_width) if isinstance(max_video_width, int) and max_video_width > 0 else MAX_VIDEO_WIDTH
    

    # Validate file
    if not validate_video_file(input_path):
        return delete_original, 0, "skip-invalid", "unknown | length unknown | fps unknown"

    transcode_state = inspect_transcoding_need(input_path)
    if transcode_state == "invalid":
        return delete_original, 0, "skip-invalid", "unknown | length unknown | fps unknown"
    if transcode_state == "already-av1":
        if reencode_av1:
            pass
        elif prompt_av1:
            if not maybe_reencode_existing_av1(input_path, auto_reencode=False):
                return delete_original, 0, "skip-av1", "unknown | length unknown | fps unknown"
        else:
            cprint(
                f"⏭️  Skipping: {display_name} (already AV1; use --prompt-av1 or --reencode-av1)",
                "info",
                log_body=f"⏭️  Skipping: {display_name_log} (already AV1; use --prompt-av1 or --reencode-av1)",
            )
            return delete_original, 0, "skip-av1", "unknown | length unknown | fps unknown"
    elif transcode_state != "needs":
        cprint(
            f"⏭️  Skipping: {display_name} (already using target codec)",
            "info",
            log_body=f"⏭️  Skipping: {display_name_log} (already using target codec)",
        )
        return delete_original, 0, "skip-codec", "unknown | length unknown | fps unknown"

    # Get file size (used for display and progress)
    try:
        file_size_bytes = os.path.getsize(input_path)
        if not _SUPPRESS_OUTPUT:
            cprint(f"   Filesize:   {_format_size(float(file_size_bytes))}", "info")
    except Exception as e:
        file_size_bytes = 0
        if not _SUPPRESS_OUTPUT:
            cprint(f"Could not determine file size: {e}", "warning")

    output_dir, output_path, temp_output = _build_output_paths(
        input_path,
        output_dir,
        ACTIVE_ENCODER["codec"],
    )
    
    # Check disk space before proceeding (skip in dry run)
    if not dry_run:
        if not check_disk_space(input_path, output_dir):
            return delete_original, 0, "skip-disk", "unknown | length unknown | fps unknown"

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        effective_overwrite = overwrite or _AUTO_OVERWRITE_EXISTING
        if not effective_overwrite:
            if _NO_PROMPT:
                return delete_original, 0, "skip-overwrite", "unknown | length unknown | fps unknown"
            existing_output = _display_path(output_path, full_path=True, fallback_label="output file")
            resp = safe_input(
                PROMPT_YES_NO_ALL,
                message=f"Output file exists — delete it and re-encode?\n{existing_output}",
            ).strip().lower()
            if resp in ("a", "all"):
                _AUTO_OVERWRITE_EXISTING = True
            elif resp not in ("y", "yes"):
                return delete_original, 0, "skip-overwrite", "unknown | length unknown | fps unknown"

    # Probe once and reuse metadata for bitrate decisions + user-facing output.
    stream_info = get_video_stream_info(input_path)
    width = stream_info.get("width")
    height = stream_info.get("height")
    fps = stream_info.get("fps")
    duration = stream_info.get("duration")
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        res_str = f"{width}x{height}"
    else:
        res_str = "unknown"
    fps_str = _format_fps_display(fps)
    bitrate_str = _format_bitrate_display(stream_info.get("bitrate"))
    media_info = _build_media_info(stream_info)

    # --- CALCULATE TARGET BITRATE ---
    target_bitrate_int = 0
    bitrate_decision = "auto"
    if bitrate:
        try:
            target_bitrate_int = _parse_bitrate_to_bps(bitrate)
            bitrate_decision = f"manual {target_bitrate_int/1_000_000:.2f}M"
        except ValueError:
            cprint(f"Invalid bitrate format: {bitrate}. Using auto-detection.", "warning")
            bitrate = None
    
    if not bitrate:
        input_bitrate = stream_info.get("bitrate")

        if isinstance(input_bitrate, int) and input_bitrate > 0:
            recommended_bitrate = None
            if isinstance(width, int) and isinstance(height, int) and isinstance(fps, (int, float)) and fps > 0:
                recommended_bitrate = get_recommended_bitrate(width, height, float(fps))

            if recommended_bitrate and input_bitrate <= int(recommended_bitrate * RECOMMENDED_BITRATE_MARGIN):
                # Already efficient for this resolution/FPS: keep source bitrate.
                target_bitrate_int = input_bitrate
                bitrate_decision = (
                    f"kept {input_bitrate/1_000_000:.2f}M "
                    f"(<= rec {recommended_bitrate/1_000_000:.2f}M @ {width}x{height} {float(fps):.2f}fps)"
                )
            else:
                target_bitrate_int = int(input_bitrate * BITRATE_REDUCTION_FACTOR)
                bitrate_decision = f"reduced {input_bitrate/1_000_000:.2f}M→{target_bitrate_int/1_000_000:.2f}M"
        else:
            if not _SUPPRESS_OUTPUT:
                cprint(f"⚠️  Bitrate unknown, using {BITRATE_FALLBACK/1_000_000:.1f}M fallback", "warning")
            target_bitrate_int = BITRATE_FALLBACK
            bitrate_decision = f"fallback {BITRATE_FALLBACK/1_000_000:.1f}M"

    _pre_cap_bps = target_bitrate_int
    try:
        _in_sz = os.path.getsize(input_path)
    except OSError:
        _in_sz = 0
    target_bitrate_int, _cap_notes = apply_output_size_bitrate_caps(
        target_bitrate_int,
        input_file_bytes=_in_sz,
        duration_sec=float(duration) if isinstance(duration, (int, float)) and duration > 0 else None,
        input_stream_bps=stream_info.get("bitrate") if isinstance(stream_info.get("bitrate"), int) else None,
        max_output_bytes=max_output_bytes,
        min_shrink_percent=min_shrink_percent,
    )
    if _cap_notes and target_bitrate_int < _pre_cap_bps:
        bitrate_decision = f"{bitrate_decision} | cap: {', '.join(_cap_notes)} → {target_bitrate_int/1_000_000:.2f}M"

    if not _SUPPRESS_OUTPUT:
        cprint(
            f"🎯 {display_name} → {bitrate_decision}",
            "info",
            log_body=f"🎯 {display_name_log} → {bitrate_decision}",
        )
        cprint(f"   Resolution: {res_str}", "info")
        cprint(f"   FPS:        {fps_str}", "info")
        cprint(f"   Bitrate:    {bitrate_str}", "info")
        cprint(f"   Filesize:   {_format_size(float(file_size_bytes)) if file_size_bytes > 0 else 'unknown'}", "info")
        cprint(f"   Duration:   {_format_duration(duration)}", "info")

    # --- ENCODER SPECIFIC SETTINGS ---
    encoder_name = ACTIVE_ENCODER["encoder"]
    hw_type = ACTIVE_ENCODER["hw_type"]
    codec = ACTIVE_ENCODER["codec"]

    audio_channels = get_audio_channels(input_path)
    command, pix_fmt = _build_ffmpeg_command(
        ffmpeg_cmd=FFMPEG_CMD,
        input_path=input_path,
        output_path=output_path,
        temp_output=temp_output,
        encoder_name=encoder_name,
        hw_type=hw_type,
        codec=codec,
        target_bitrate_int=target_bitrate_int,
        effective_cpu_threads=effective_cpu_threads,
        effective_max_width=effective_max_width,
        audio_channels=audio_channels,
    )

    if not _SUPPRESS_OUTPUT:
        cprint(f"   Encoder: {encoder_name} ({codec.upper()}, {hw_type.upper()})", "info")
        if hw_type == "cpu":
            cprint(f"   CPU threads: {effective_cpu_threads}", "info")
        # Show ffmpeg path for debugging
        if os.getenv("AV1_DEBUG"):
            cprint(f"   FFmpeg: {FFMPEG_CMD}", "info")
            if _HIDE_FILENAMES:
                cprint("   Command: hidden due to --hide-filenames", "info")
            else:
                cprint(f"   Command: {' '.join(command)}", "info")
    # Initialize per-file event context
    file_event = {
        "file": _display_path(input_path, full_path=True, fallback_label="hidden"),
        "output": _display_path(output_path, full_path=True, fallback_label="hidden"),
        "encoder": encoder_name,
        "codec": codec,
        "target_bps": target_bitrate_int,
    }
    if max_output_bytes is not None:
        file_event["max_output_bytes"] = max_output_bytes
    if min_shrink_percent is not None:
        file_event["min_shrink_percent"] = min_shrink_percent
    retry_options = ConversionRetryOptions(
        input_path=input_path,
        output_dir=output_dir,
        bitrate=bitrate,
        delete_original=delete_original,
        overwrite=overwrite,
        dry_run=dry_run,
        keep_mkv=keep_mkv,
        show_progress=show_progress,
        batch_index=batch_index,
        batch_total=batch_total,
        progress_label=progress_label,
        progress_callback=progress_callback,
        cpu_threads=cpu_threads,
        prompt_av1=prompt_av1,
        reencode_av1=reencode_av1,
        max_output_bytes=max_output_bytes,
        min_shrink_percent=min_shrink_percent,
        max_video_width=max_video_width,
    )

    # Dry run: Show planned command and summary, then return without executing
    if dry_run:
        summary = {
            "input": input_path,
            "output": output_path,
            "encoder": encoder_name,
            "codec": codec,
            "pix_fmt": pix_fmt,
            "bitrate": target_bitrate_int,
        }
        if max_output_bytes is not None:
            summary["max_output_bytes"] = max_output_bytes
        if min_shrink_percent is not None:
            summary["min_shrink_percent"] = min_shrink_percent
        if not _SUPPRESS_OUTPUT:
            cprint("🔍 Dry run: Planned conversion", "info")
            # Format summary dict for display
            display_summary = summary.copy()
            display_summary_log = summary.copy()
            if _HIDE_FILENAMES:
                display_summary["input"] = _display_path(input_path)
                display_summary["output"] = _display_path(output_path, fallback_label="output file")
                display_summary_log = display_summary
            else:
                display_summary_log["input"] = _display_path(input_path, full_path=True)
                display_summary_log["output"] = _display_path(output_path, full_path=True)
            summary_str = "\n".join(f"  {k}: {v}" for k, v in display_summary.items())
            summary_str_log = "\n".join(f"  {k}: {v}" for k, v in display_summary_log.items())
            cprint(f"Summary:\n{summary_str}", "info", log_body=f"Summary:\n{summary_str_log}")
        try:
            dry_data = {
                **summary,
                "input": _display_path(input_path, full_path=True, fallback_label="hidden"),
                "output": _display_path(output_path, full_path=True, fallback_label="hidden"),
            }
            _LOG_EVENTS.append({
                "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                "level": "info",
                "message": "dry_run_summary",
                "data": dry_data,
            })
        except Exception:
            pass
        return delete_original, 0, f"dry-run {bitrate_decision}", media_info
    
    # Get video duration for progress calculation (prefer already-probed metadata)
    total_duration = float(duration) if isinstance(duration, (int, float)) and duration > 0 else None
    
    # Collect output for error reporting
    error_lines = []
    
    try:
        # Run ffmpeg with machine-readable progress updates.
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )

        file_task = None
        if _PROGRESS_CONTEXT and show_progress:
            file_size_str = _format_size(file_size_bytes) if file_size_bytes > 0 else ""
            file_task = _PROGRESS_CONTEXT.add_task(
                _format_file_progress_description(progress_name, batch_index, batch_total),
                total=100 if total_duration else None,
                fps=_progress_field(""),
                eta=_progress_field(""),
                size=_progress_field(file_size_str),
                saved=_progress_field(""),
                progress_text=_progress_field(_format_progress_clock(0, total_duration)),
            )

        progress_state: dict[str, str] = {}
        try:
            for raw_line in _iter_ffmpeg_output_with_stall_timeout(process, command, FFMPEG_STALL_TIMEOUT):
                line = raw_line.strip()
                if not line:
                    continue

                if "=" in line:
                    key, value = line.split("=", 1)
                    progress_state[key.strip()] = value.strip()

                    if key.strip() == "progress":
                        current_time = _parse_ffmpeg_out_time(progress_state.get("out_time", ""))
                        progress_fraction = None
                        if total_duration and isinstance(current_time, (int, float)):
                            progress_fraction = min(max(float(current_time) / float(total_duration), 0.0), 1.0)

                        speed_value = progress_state.get("speed", "")
                        speed_number = _parse_ffmpeg_speed(speed_value)
                        eta_seconds = None
                        if total_duration and isinstance(current_time, (int, float)) and speed_number:
                            remaining = max(float(total_duration) - float(current_time), 0.0)
                            eta_seconds = remaining / speed_number if speed_number > 0 else None
                        elif total_duration and progress_fraction and progress_fraction > 0:
                            elapsed_media = max(float(current_time or 0), 0.0)
                            eta_seconds = max(float(total_duration) - elapsed_media, 0.0)

                        eta_field = "Done" if progress_state.get("progress") == "end" else f"ETA: {_format_eta_seconds(eta_seconds)}"
                        progress_text = _format_progress_clock(current_time, total_duration)
                        rate_text = _format_rate_display(progress_state.get("fps", ""), speed_value)

                        if file_task is not None and _PROGRESS_CONTEXT:
                            file_size_str = _format_size(file_size_bytes) if file_size_bytes > 0 else ""
                            update_kwargs = {
                                "fps": _progress_field(rate_text),
                                "eta": _progress_field(eta_field),
                                "size": _progress_field(file_size_str),
                                "progress_text": _progress_field(progress_text),
                            }
                            if progress_fraction is not None:
                                update_kwargs["completed"] = progress_fraction * 100
                            _PROGRESS_CONTEXT.update(file_task, **update_kwargs)

                        if progress_callback:
                            progress_callback(progress_fraction, progress_text, eta_field)

                        progress_state.clear()
                    continue

                line_lower = line.lower()
                if any(keyword in line_lower for keyword in ["error", "failed", "cannot", "invalid", "unsupported"]):
                    error_lines.append(line)

            process.wait()
            if file_task is not None and _PROGRESS_CONTEXT:
                file_size_str = _format_size(file_size_bytes) if file_size_bytes > 0 else ""
                final_update = {
                    "eta": _progress_field("Done"),
                    "size": _progress_field(file_size_str),
                    "progress_text": _progress_field(_format_progress_clock(total_duration, total_duration)),
                }
                if total_duration:
                    final_update["completed"] = 100
                _PROGRESS_CONTEXT.update(file_task, **final_update)
        finally:
            if file_task is not None and _PROGRESS_CONTEXT:
                _PROGRESS_CONTEXT.remove_task(file_task)

        result = process
    except Exception as e:
        cprint(f"FFmpeg execution error: {e}", "error")
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError:
                pass
        return delete_original, 0, bitrate_decision, media_info

    if result.returncode == 0:
        try:
            if os.path.exists(temp_output) and os.path.getsize(temp_output) > MIN_FILE_SIZE_BYTES:
                os.replace(temp_output, output_path)
                file_size = os.path.getsize(input_path)
                new_file_size = os.path.getsize(output_path)
                size_saved = file_size - new_file_size
                saved_percent = (size_saved / file_size) * 100 if file_size > 0 else 0
                _log_path = _display_path(input_path, full_path=True, fallback_label="hidden")
                mb_before = file_size / (1024**2)
                mb_after = new_file_size / (1024**2)
                mb_saved = size_saved / (1024**2)
                cprint(
                    f"Complete: {mb_before:.2f} MB → {mb_after:.2f} MB",
                    "success",
                    log_body=(
                        f"{_log_path} | before: {mb_before:.2f} MB ({file_size} bytes) | "
                        f"after: {mb_after:.2f} MB ({new_file_size} bytes)"
                    ),
                    log_only=_SUPPRESS_OUTPUT,
                )
                cprint(
                    f"   Saved: {mb_saved:.2f} MB ({saved_percent:.1f}%)",
                    "success",
                    log_body=(
                        f"{_log_path} | saved: {mb_saved:.2f} MB ({saved_percent:.1f}% of input) | "
                        f"{size_saved} bytes"
                    ),
                    log_only=_SUPPRESS_OUTPUT,
                )
                # Record per-file metrics
                try:
                    _LOG_EVENTS.append({
                        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                        "level": "success",
                        "message": "file_metrics",
                        "data": {
                            **file_event,
                            "original_bytes": file_size,
                            "new_bytes": new_file_size,
                            "saved_bytes": size_saved,
                            "saved_percent": saved_percent,
                            "duration": total_duration,
                        }
                    })
                except Exception:
                    pass
                
                if file_size <= new_file_size:
                    cprint(
                        "Warning: Output file is larger than input (entropy/quality issue)",
                        "warning",
                        log_body=(
                            f"{_log_path} | output not smaller than input "
                            f"(before {mb_before:.2f} MB / {file_size} bytes, "
                            f"after {mb_after:.2f} MB / {new_file_size} bytes)"
                        ),
                        log_only=_SUPPRESS_OUTPUT,
                    )
                    delete_original = _finalize_output_file(input_path, output_path, keep_mkv, delete_original)
                else:
                    delete_original = _finalize_output_file(input_path, output_path, keep_mkv, delete_original)
                
                return delete_original, size_saved, bitrate_decision, media_info
            else:
                cprint("❌ Error: Temp file missing or invalid!", "error")
        except OSError as e:
            cprint(f"❌ Error swapping files: {e}", "error")
    else:
        cprint(f"❌ Conversion failed (exit code: {result.returncode})", "error")
        # Show relevant error messages from ffmpeg output
        if error_lines:
            # Show last few error lines (most relevant are usually at the end)
            relevant_errors = error_lines[-5:] if len(error_lines) > 5 else error_lines
            cprint("FFmpeg error output:", "error")
            for err_line in relevant_errors:
                if err_line:  # Skip empty lines
                    cprint(f"   {err_line}", "error")
            
            # Check for libva ABI mismatch errors and provide guidance/retry
            # Only check for libva errors if we're using a hardware encoder (vaapi specifically)
            error_text = " ".join(error_lines).lower()
            is_hardware_encoder = ACTIVE_ENCODER["hw_type"] in ("vaapi", "nvidia", "amd")
            
            # More specific libva indicators - these are libva-specific errors
            libva_specific_indicators = [
                "failed to resolve symbol", "vamapbuffer2", "libva.so", 
                "error reinitializing filters", "function not implemented"
            ]
            # Only consider it a libva error if:
            # 1. We're using hardware encoding (especially vaapi)
            # 2. AND we see libva-specific error messages
            is_libva_error = (is_hardware_encoder and 
                            ACTIVE_ENCODER["hw_type"] == "vaapi" and
                            any(indicator in error_text for indicator in libva_specific_indicators))
            
            if is_libva_error:
                cprint("\n⚠️  Hardware encoding failed due to libva ABI mismatch with PATH ffmpeg.", "warning")
                
                # Try system ffmpeg for hardware encoding if auto-fallback is enabled
                fallback_env = os.getenv("AV1_FFMPEG_FALLBACK", "auto")
                should_try_system_ffmpeg = (fallback_env == "auto" or _env_bool(fallback_env))
                
                if should_try_system_ffmpeg and ACTIVE_ENCODER["hw_type"] != "cpu" and FFMPEG_CMD != "/usr/bin/ffmpeg":
                    system_ffmpeg = "/usr/bin/ffmpeg"
                    if os.path.exists(system_ffmpeg):
                        cprint("🔄 Retrying hardware encoding with system ffmpeg (compatible with libva)...", "info")
                        original_ffmpeg = FFMPEG_CMD
                        FFMPEG_CMD = system_ffmpeg
                        
                        # Clean up failed temp file
                        if os.path.exists(temp_output):
                            try:
                                os.remove(temp_output)
                            except Exception:
                                pass
                        
                        # Retry with system ffmpeg
                        try:
                            result = _retry_convert_single_file(retry_options)
                            # Keep system ffmpeg for this session (hardware encoding works)
                            return result
                        except Exception:
                            # Restore PATH ffmpeg on failure
                            FFMPEG_CMD = original_ffmpeg
                            raise
                
                # Auto-retry with CPU encoding if hardware encoding failed (still using PATH ffmpeg)
                if ACTIVE_ENCODER["hw_type"] != "cpu":
                    cprint("🔄 Automatically retrying with CPU encoding (still using PATH ffmpeg)...", "info")
                    
                    # Save original encoder first
                    original_encoder = ACTIVE_ENCODER.copy()
                    
                    # Verify CPU encoder is available before retrying
                    if not check_encoder_support("libsvtav1"):
                        cprint("❌ CPU encoder (libsvtav1) not available in PATH ffmpeg.", "error")
                        cprint("   Your PATH ffmpeg may not have libsvtav1 support compiled in.", "warning")
                        cprint("   Try: Set AV1_FFMPEG_FALLBACK=true to use system ffmpeg", "info")
                        # Restore original encoder
                        ACTIVE_ENCODER = original_encoder
                    else:
                        # Switch to CPU temporarily
                        ACTIVE_ENCODER = {"encoder": "libsvtav1", "codec": "av1", "hw_type": "cpu"}
                        
                        # Clean up failed temp file
                        if os.path.exists(temp_output):
                            try:
                                os.remove(temp_output)
                            except Exception:
                                pass
                        
                        # Retry conversion with CPU encoder
                        try:
                            result = _retry_convert_single_file(retry_options)
                            # Restore original encoder after retry
                            ACTIVE_ENCODER = original_encoder
                            return result
                        except Exception:
                            # Restore original encoder even on exception
                            ACTIVE_ENCODER = original_encoder
                            raise
                else:
                    cprint("   Solutions:", "info")
                    cprint("   1. Use system ffmpeg: Set AV1_FFMPEG_FALLBACK=true", "info")
                    cprint("   2. Fix libva compatibility: Update libva libraries to match your ffmpeg build", "info")
            elif ACTIVE_ENCODER["hw_type"] == "cpu":
                # CPU encoding failure - different issue, not libva
                cprint("\n⚠️  CPU encoding failed. This may indicate an issue with:", "warning")
                cprint("   • FFmpeg build compatibility", "info")
                cprint("   • Input file format/corruption", "info")
                cprint("   • Missing codec support (libsvtav1)", "info")
                cprint("   Try: Set AV1_FFMPEG_FALLBACK=true to use system ffmpeg", "info")
            else:
                # Other hardware encoding failure (not libva)
                cprint("\n⚠️  Hardware encoding failed (non-libva error).", "warning")
                cprint("   Try: Set AV1_FFMPEG_FALLBACK=true to use system ffmpeg", "info")
        
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except Exception as e:
                cprint(f"Could not remove temp file: {e}", "warning")

    return delete_original, 0, bitrate_decision, media_info

# ============================================================================ #
#                      FUNCTION: process_batch_files                           #
# ============================================================================ #
def process_batch_files(
    video_files: list[str],
    output_dir: Optional[str],
    input_path: str,
    bitrate: Optional[str],
    delete_original: bool,
    overwrite: bool,
    dry_run: bool,
    keep_mkv: bool,
    recursive: bool = False,
    transient_progress: bool = True,
    cpu_threads: Optional[int] = None,
    prompt_av1: bool = False,
    reencode_av1: bool = False,
    *,
    max_output_bytes: Optional[int] = None,
    min_shrink_percent: Optional[float] = None,
    max_video_width: Optional[int] = None,
) -> None:
    """
    Process a batch of video files with progress tracking and statistics.
    
    Args:
        video_files: List of file paths to process
        output_dir: Optional output directory (None means same as input)
        input_path: Base input path (for relative path display)
        bitrate: Optional bitrate override
        delete_original: Whether to auto-delete originals
        overwrite: Whether to overwrite existing files
        dry_run: If True, only show what would be done
        keep_mkv: Whether to keep .mkv extension
        recursive: Whether processing is recursive (affects display paths)
        transient_progress: Whether progress bar should be transient
    """
    if not video_files:
        return

    batch_input_bytes_total, batch_input_stat_ok = _sum_existing_file_sizes(video_files)
    n_files = len(video_files)
    if batch_input_stat_ok == 0:
        batch_size_label = "unknown"
    elif batch_input_stat_ok == n_files:
        batch_size_label = _format_size(float(batch_input_bytes_total))
    else:
        batch_size_label = (
            f"{_format_size(float(batch_input_bytes_total))} "
            f"({batch_input_stat_ok}/{n_files} readable)"
        )
    cprint(f"\n📦 Total input size: {batch_size_label} ({n_files} file(s))\n", "info")

    # Track statistics for batch summary
    total_original_size = 0
    total_new_size = 0
    files_converted = 0
    per_file_stats: list[Tuple[str, str, int, int, float]] = []
    cumulative_saved = 0
    batch_start_time = time.time()
    file_times: list[float] = []
    
    # Set up graceful cancellation handler
    global _USER_CANCELLED
    _USER_CANCELLED = False
    previous_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _signal_handler)
    
    try:
        with _build_progress(transient=transient_progress, batch_mode=True) as progress:
            global _PROGRESS_CONTEXT, _SUPPRESS_OUTPUT
            _PROGRESS_CONTEXT = progress
            overall_task = progress.add_task(
                _format_batch_progress_description(0, len(video_files), 0, "waiting..."),
                total=len(video_files),
                progress_text=_progress_field(_format_batch_elapsed_text(0)),
                saved=_progress_field(_format_saved(0)),
                size=_progress_field(""),
                eta=_progress_field(""),
            )
            auto_delete = delete_original
            last_logged_dir: Optional[str] = None

            for idx, file_path in enumerate(video_files, 1):
                # Check if user cancelled
                if _USER_CANCELLED:
                    progress.console.print("[yellow]\n⏸️  Batch conversion interrupted. Finishing current file...[/]")
                    break

                try:
                    current_dir = os.path.dirname(os.path.normpath(os.path.abspath(file_path)))
                except Exception:
                    current_dir = ""
                if current_dir != last_logged_dir:
                    _append_log_directory_header(current_dir if current_dir else os.getcwd())
                    last_logged_dir = current_dir

                # Show relative path for recursive mode
                display_path = _display_batch_item(file_path, input_path, recursive, idx, len(video_files))
                file_start = time.time()
                elapsed = int(time.time() - batch_start_time)
                completed_before_current = idx - 1

                progress.update(
                    overall_task,
                    description=_format_batch_progress_description(idx, len(video_files), elapsed, display_path),
                    completed=completed_before_current,
                    progress_text=_progress_field(_format_batch_elapsed_text(elapsed)),
                    saved=_progress_field(_format_saved(cumulative_saved)),
                    size=_progress_field(""),
                    eta=_progress_field(_format_batch_eta_text(completed_before_current, len(video_files), elapsed)),
                )
                
                # Capture original size before conversion
                try:
                    original_size = os.path.getsize(file_path)
                except OSError:
                    original_size = 0
                current_size_text = _format_size(float(original_size)) if original_size > 0 else "unknown"

                progress.update(
                    overall_task,
                    size=_progress_field(current_size_text),
                )
                
                # Determine output directory
                if output_dir and output_dir != input_path:
                    # User provided explicit output directory - preserve folder structure
                    rel_dir = os.path.dirname(os.path.relpath(file_path, input_path))
                    current_output_dir = os.path.join(output_dir, rel_dir) if rel_dir else output_dir
                else:
                    # No explicit output dir or same as input - use file's own directory
                    current_output_dir = resolve_output_dir(None, file_path)
                
                # Suppress output during conversion
                _SUPPRESS_OUTPUT = True

                def _update_batch_progress(current_fraction: Optional[float], _current_progress_text: str, _current_eta: str) -> None:
                    elapsed_now = int(time.time() - batch_start_time)
                    completed_value = idx - 1
                    if isinstance(current_fraction, (int, float)):
                        completed_value += min(max(float(current_fraction), 0.0), 1.0)
                    progress.update(
                        overall_task,
                        description=_format_batch_progress_description(idx, len(video_files), elapsed_now, display_path),
                        completed=completed_value,
                        progress_text=_progress_field(_format_batch_elapsed_text(elapsed_now)),
                        saved=_progress_field(_format_saved(cumulative_saved)),
                        size=_progress_field(current_size_text),
                        eta=_progress_field(_format_batch_eta_text(completed_value, len(video_files), elapsed_now)),
                    )

                auto_delete_result, size_saved, bitrate_decision, media_info = convert_single_file(
                    file_path,
                    current_output_dir,
                    bitrate,
                    auto_delete,
                    overwrite,
                    dry_run,
                    keep_mkv,
                    show_progress=True,
                    batch_index=idx,
                    batch_total=len(video_files),
                    progress_label=display_path,
                    progress_callback=_update_batch_progress,
                    cpu_threads=cpu_threads,
                    prompt_av1=prompt_av1,
                    reencode_av1=reencode_av1,
                    max_output_bytes=max_output_bytes,
                    min_shrink_percent=min_shrink_percent,
                    max_video_width=max_video_width,
                )
                _SUPPRESS_OUTPUT = False
                
                # Track statistics if conversion happened
                if size_saved != 0:
                    files_converted += 1
                    total_original_size += original_size
                    total_new_size += (original_size - size_saved)
                    cumulative_saved += size_saved
                    saved_percent = (size_saved / original_size * 100) if original_size > 0 else 0
                    per_file_stats.append(
                        (
                            display_path,
                            _display_path(file_path, full_path=True, fallback_label="hidden"),
                            original_size,
                            size_saved,
                            saved_percent,
                        )
                    )
                    
                    # Track file encoding time for ETA
                    file_time = time.time() - file_start
                    file_times.append(file_time)
                
                # Update auto-delete flag based on user's "all" choice
                if auto_delete_result:
                    auto_delete = True

                elapsed = int(time.time() - batch_start_time)
                completed_after_current = idx

                progress.update(
                    overall_task,
                    description=_format_batch_progress_description(idx, len(video_files), elapsed, display_path),
                    completed=completed_after_current,
                    progress_text=_progress_field(_format_batch_elapsed_text(elapsed)),
                    saved=_progress_field(_format_saved(cumulative_saved)),
                    size=_progress_field(current_size_text),
                    eta=_progress_field(_format_batch_eta_text(completed_after_current, len(video_files), elapsed)),
                )

            _PROGRESS_CONTEXT = None
    finally:
        signal.signal(signal.SIGINT, previous_sigint_handler)
    
    # Display batch summary
    batch_elapsed = int(time.time() - batch_start_time)
    status_msg = "interrupted" if _USER_CANCELLED else "complete"
    
    cprint(f"\n{'='*60}", "info")
    cprint(f"📊 Batch conversion {status_msg}!", "success" if not _USER_CANCELLED else "warning")
    cprint(f"{'='*60}", "info")
    
    cprint("\n📈 Processing Summary:", style="bold cyan")
    cprint(f"   Files processed:  {len(video_files)}", "info")
    cprint(f"   Files converted:  {files_converted}", "success" if files_converted > 0 else "info")
    cprint(f"   Files skipped:    {len(video_files) - files_converted}", "info")
    cprint(f"   Time elapsed:     {batch_elapsed // 60}m {batch_elapsed % 60}s", "info")
    
    if files_converted == 0:
        cprint("\n💡 No files were converted (already using target codec or errors occurred).", "info")
        return
    
    if total_original_size > 0:
        total_saved = total_original_size - total_new_size
        percent_saved = (total_saved / total_original_size) * 100
        
        # Show per-file stats if we have them
        if per_file_stats and len(per_file_stats) <= 10:
            cprint("\n📋 Per-File Results:", style="bold cyan")
            for filename, filename_log, orig_size, saved, percent in per_file_stats:
                status = "✅" if saved > 0 else "⚠️"
                styled_name = _styled_filename(filename)
                cprint(
                    f"   {status} {styled_name}: {saved / (1024**2):.2f} MB saved ({percent:.1f}%)",
                    "info",
                    markup=True,
                    log_body=(
                        f"   {status} {filename_log}: saved {saved / (1024**2):.2f} MB ({percent:.1f}%) "
                        f"| {saved} bytes of {orig_size} bytes input"
                    ),
                )
        elif per_file_stats:
            cprint("\n📋 Showing top 10 files by space saved:", style="bold cyan")
            top_files = sorted(per_file_stats, key=lambda x: x[3], reverse=True)[:10]
            for filename, filename_log, orig_size, saved, percent in top_files:
                styled_name = _styled_filename(filename)
                cprint(
                    f"   ✅ {styled_name}: {saved / (1024**2):.2f} MB saved ({percent:.1f}%)",
                    "info",
                    markup=True,
                    log_body=(
                        f"   ✅ {filename_log}: saved {saved / (1024**2):.2f} MB ({percent:.1f}%) "
                        f"| {saved} bytes of {orig_size} bytes input"
                    ),
                )
        
        cprint("\n💾 Total Space Savings:", style="bold cyan")
        cprint(
            f"   Before:  {total_original_size / (1024**3):.2f} GB",
            "info",
            log_body=f"   Before:  {total_original_size / (1024**3):.2f} GB ({total_original_size} bytes total)",
        )
        cprint(
            f"   After:   {total_new_size / (1024**3):.2f} GB",
            "info",
            log_body=f"   After:   {total_new_size / (1024**3):.2f} GB ({total_new_size} bytes total)",
        )
        cprint(
            f"   Saved:   {total_saved / (1024**3):.2f} GB ({percent_saved:.1f}%)",
            "success",
            log_body=(
                f"   Saved:   {total_saved / (1024**3):.2f} GB ({percent_saved:.1f}%) "
                f"| {total_saved} bytes freed vs input total"
            ),
        )
        
        if batch_elapsed > 0:
            avg_time = batch_elapsed / files_converted
            cprint(f"   Average: {avg_time:.1f}s per file", "info")
    
    cprint(f"{'='*60}\n", "info")
    
    # Emit batch summary event for JSON logs
    if total_original_size > 0:
        try:
            total_saved = total_original_size - total_new_size
            percent_saved = (total_saved / total_original_size) * 100
            _LOG_EVENTS.append({
                "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                "level": "success",
                "message": "batch_summary",
                "data": {
                    "files_total": len(video_files),
                    "files_converted": files_converted,
                    "original_bytes_total": total_original_size,
                    "new_bytes_total": total_new_size,
                    "saved_bytes_total": total_saved,
                    "saved_percent_total": percent_saved,
                    "elapsed_seconds": int(time.time() - batch_start_time),
                }
            })
        except Exception:
            pass

# ============================================================================ #
#                           FUNCTION: convert_videos                           #
# ============================================================================ #
def convert_videos(
    input_path: str,
    output_dir: Optional[str] = None,
    bitrate: Optional[str] = None,
    delete_original: bool = False,
    overwrite: bool = False,
    dry_run: bool = False,
    recursive: bool = False,
    keep_mkv: bool = False,
    cpu_threads: Optional[int] = None,
    prompt_av1: bool = False,
    reencode_av1: bool = False,
    *,
    max_output_bytes: Optional[int] = None,
    min_shrink_percent: Optional[float] = None,
    max_video_width: Optional[int] = None,
) -> None:
    """
    Main entry point for converting videos.
    Handles both single files and directory processing.
    Supports recursive subdirectory traversal when recursive=True.
    """
    if os.path.isfile(input_path):
        # Single file - set up progress context for progress bar
        global _PROGRESS_CONTEXT, _USER_CANCELLED
        _USER_CANCELLED = False
        previous_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, _signal_handler)
        with _build_progress(transient=False, batch_mode=False) as progress:
            _PROGRESS_CONTEXT = progress
            try:
                convert_single_file(
                    input_path,
                    output_dir,
                    bitrate,
                    delete_original,
                    overwrite,
                    dry_run,
                    keep_mkv,
                    show_progress=True,
                    cpu_threads=cpu_threads,
                    prompt_av1=prompt_av1,
                    reencode_av1=reencode_av1,
                    max_output_bytes=max_output_bytes,
                    min_shrink_percent=min_shrink_percent,
                    max_video_width=max_video_width,
                )
            finally:
                _PROGRESS_CONTEXT = None
                signal.signal(signal.SIGINT, previous_sigint_handler)
    elif os.path.isdir(input_path):
        if output_dir is None:
            output_dir = input_path
        else:
            os.makedirs(output_dir, exist_ok=True)
        
        # Collect all video files (recursively or not)
        video_files = _collect_directory_video_files(input_path, recursive)
        
        if not video_files:
            mode = "directory tree" if recursive else "directory"
            cprint(f"❌ No video files found in {mode}.", "warning")
            return
        
        # Sort files alphabetically for consistent processing order
        video_files.sort()
        
        mode_str = "recursively" if recursive else "in directory"
        cprint(f"🔍 Found {len(video_files)} video file(s) {mode_str}.\n", "info")
        
        # Process batch using shared helper function
        process_batch_files(
            video_files,
            output_dir,
            input_path,
            bitrate,
            delete_original,
            overwrite,
            dry_run,
            keep_mkv,
            recursive,
            transient_progress=True,
            cpu_threads=cpu_threads,
            prompt_av1=prompt_av1,
            reencode_av1=reencode_av1,
            max_output_bytes=max_output_bytes,
            min_shrink_percent=min_shrink_percent,
            max_video_width=max_video_width,
        )
    else:
        cprint("❌ Invalid path: File or directory does not exist.", "error")

def list_videos(
    input_paths: Optional[list[str]] = typer.Argument(
        None,
        help="Files, directories, or wildcard patterns to scan. Default: current working directory.",
    ),
    recursive: bool = typer.Option(
        False,
        "-r",
        "--recursive",
        help="Include videos in subfolders (walk the directory tree).",
        rich_help_panel="File Handling",
    ),
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable ANSI/Rich colors in the table output.",
        rich_help_panel="Display",
    ),
    hide_filenames: bool = typer.Option(
        False,
        "--hide-filenames",
        help="Redact filenames in the table (use placeholder labels).",
        rich_help_panel="Display",
    ),
    ffprobe: Optional[str] = typer.Option(
        None,
        "--ffprobe",
        help="Path to the ffprobe executable. Default: AV1_FFPROBE_PATH, PATH, or 'ffprobe'.",
        rich_help_panel="FFmpeg",
    ),
) -> None:
    """List video files (by supported extension) and show each file's video codec and size."""
    _run_list_command(
        input_paths,
        recursive=recursive,
        no_color=no_color,
        hide_filenames=hide_filenames,
        ffprobe_path=ffprobe,
    )


app.command("list")(list_videos)
app.command("ls", hidden=True)(list_videos)


def help_cmd(
    ctx: typer.Context,
    topic: Optional[str] = typer.Argument(
        None,
        help=(
            "Subcommand to show help for (e.g. [bold]main[/], [bold]list[/], [bold]clean[/]). "
            "Omit to show the top-level [bold]av1[/] command list (all subcommands)."
        ),
    ),
) -> None:
    """Show help: top-level subcommands (no topic), or help for a specific subcommand (e.g. [bold]main[/])."""
    parent = ctx.parent
    if parent is None or not isinstance(parent.command, click.Group):
        typer.echo("Internal error: missing CLI group context.", err=True)
        raise typer.Exit(code=1)

    if not (topic and topic.strip()):
        typer.echo(parent.command.get_help(parent))
        raise typer.Exit(0)

    name = topic.strip()
    sub = parent.command.get_command(parent, name)
    if sub is None:
        typer.echo(
            f"Unknown subcommand: {name!r}. Run {__app_name__} help to see available commands.",
            err=True,
        )
        raise typer.Exit(code=1)
    with click.Context(sub, parent=parent, info_name=name) as subctx:
        typer.echo(sub.get_help(subctx))
    raise typer.Exit(0)


def version_cmd() -> None:
    """Show this program's version, Python, build stamp, ffmpeg, and detected encoder (same as [bold]--version[/] on the compressor)."""
    _version_callback(True)


app.command("help")(help_cmd)
app.command("version")(version_cmd)


def _run_cleanup_command(input_paths: Optional[list[str]], recursive: bool) -> None:
    """Shared implementation for cleanup command aliases."""
    resolved_input_paths = input_paths or [os.getcwd()]
    _confirm_root_like_input_paths(resolved_input_paths, intent="clean", recursive=recursive)
    cleanup_targets = _resolve_cleanup_targets(resolved_input_paths, recursive=recursive)

    if not cleanup_targets:
        mode = "recursively" if recursive else "without recursion"
        cprint(
            f"No stale temp files ({TEMP_OUTPUT_SUFFIX}) found {mode} in the provided locations.",
            "info",
        )
        return

    cprint(f"Found {len(cleanup_targets)} temp file(s) to remove.", "info")
    removed_count, failed_count = _remove_cleanup_targets(cleanup_targets)
    cprint(
        f"Cleanup complete: removed={removed_count}, failed={failed_count}",
        "success" if failed_count == 0 else "warning",
    )


@app.command("clean")
def clean(
    input_paths: Optional[list[str]] = typer.Argument(
        None,
        help="Optional files, folders, or wildcard patterns to clean. Default: current working directory.",
    ),
    recursive: bool = typer.Option(
        False,
        "-r",
        "--recursive",
        help="Scan folders recursively for stale temp files.",
        rich_help_panel="File Handling",
    ),
) -> None:
    """Remove stale AV1 temp files (`*.temp.mkv`) from previous runs."""
    _run_cleanup_command(input_paths, recursive=recursive)


@app.command("cleanup", hidden=True)
def cleanup_alias(
    input_paths: Optional[list[str]] = typer.Argument(
        None,
        help="Optional files, folders, or wildcard patterns to clean. Default: current working directory.",
    ),
    recursive: bool = typer.Option(
        False,
        "-r",
        "--recursive",
        help="Scan folders recursively for stale temp files.",
        rich_help_panel="File Handling",
    ),
) -> None:
    """Alias for `clean`."""
    _run_cleanup_command(input_paths, recursive=recursive)


@app.command(
    "main",
    hidden=True,
    epilog=(
        "Temp-file cleanup only: [bold]av1 clean --help[/] or use [bold]--clean[/] / [bold]--cleanup[/] above."
    ),
)
def main(
    input_paths: list[str] = typer.Argument(
        None,
        help="One or more input video files, folders, or wildcard patterns to process or probe. By default, directories are scanned non-recursively, existing AV1 files are skipped, and matching outputs are written next to the source files unless --output-dir is provided.",
    ),
    output_dir: Optional[str] = typer.Option(None, help="Write converted files to this directory. Default: save beside each input file.", rich_help_panel="Input/Output"),
    bitrate: Optional[str] = typer.Option(None, help="Force a target video bitrate (for example 2500k or 2.5m). Default: use the script's automatic bitrate logic.", rich_help_panel="Input/Output"),
    max_output_size: Optional[str] = typer.Option(
        None,
        "--max-output-size",
        "-S",
        help="Aim for output under this size (for example 10M or 500MB). Default: no explicit size cap; bitrate is chosen by the normal reduction logic. Encoders may overshoot slightly.",
        rich_help_panel="Input/Output",
    ),
    min_shrink: Optional[float] = typer.Option(
        None,
        "--min-shrink",
        help="Minimum percent reduction in file size. Default: 50, meaning the output targets at most 50% of the original size unless another constraint overrides it.",
        rich_help_panel="Input/Output",
    ),
    force: bool = typer.Option(
        False,
        "-f",
        "--force",
        help="Force post-conversion in-place behavior: equivalent to --delete-original + --rename-original for this run.",
        rich_help_panel="File Handling",
    ),
    size_preset: Optional[str] = typer.Option(
        None,
        "--size-preset",
        help="Quick filesize/resolution profile. Choices: light, balanced, aggressive. Applies defaults for shrink and max-width, but explicit flags still win.",
        rich_help_panel="Input/Output",
    ),
    max_width: Optional[int] = typer.Option(
        None,
        "--max-width",
        help=f"Override maximum output width used by the scale filter. Default: {MAX_VIDEO_WIDTH} (or preset value when --size-preset is set).",
        rich_help_panel="Input/Output",
    ),
    delete_original: bool = typer.Option(False, "-d", "--delete-original", help="Delete each source file after a successful conversion. Default: keep originals and, if prompts are enabled, ask before deleting.", rich_help_panel="File Handling"),
    overwrite: bool = typer.Option(False, "-o", "--overwrite", help="Replace an existing output file if one already exists. Default: skip files whose destination already exists.", rich_help_panel="File Handling"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would be converted and which settings would be used, without writing any output files.", rich_help_panel="File Handling"),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Scan folders recursively. Default: only process files in the top-level input directory.", rich_help_panel="File Handling"),
    clean_stale: bool = typer.Option(
        False,
        "--clean",
        "--cleanup",
        help="Remove stale AV1 temp files (*.temp.mkv) under the given paths (or the current directory) and exit. Does not convert. Same behavior as the `clean` subcommand.",
        rich_help_panel="File Handling",
    ),
    rename_original: bool = typer.Option(
        False,
        "-R",
        "--rename-original",
        help="Automatically rename output back to the original filename/extension when in-place renaming is possible (skip rename prompts for this run).",
        rich_help_panel="File Handling",
    ),
    keep_mkv: bool = typer.Option(False, "--keep-mkv", help="Keep the converted file as .mkv instead of renaming it back to the original extension when possible. Default: restore the original filename/extension in place when safe.", rich_help_panel="File Handling"),
    log_type: str = typer.Option("txt", "--log-type", help="Log output format: 'txt', 'html', 'json', or 'none'. Default: txt.", rich_help_panel="Logging"),
    log_dir: Optional[str] = typer.Option(None, "--log-dir", help="Directory for log files. Default: %TEMP%/av1-logs.", rich_help_panel="Logging"),
    ffmpeg: Optional[str] = typer.Option(None, "--ffmpeg", help="Path to the ffmpeg executable. Default: use the bundled/configured ffmpeg resolution logic or environment settings.", rich_help_panel="FFmpeg"),
    ffprobe: Optional[str] = typer.Option(None, "--ffprobe", help="Path to the ffprobe executable. Default: use the bundled/configured ffprobe resolution logic or environment settings.", rich_help_panel="FFmpeg"),
    cpu_threads: Optional[int] = typer.Option(
        None,
        "--cpu-threads",
        "--cpu-cores",
        help=f"Logical CPU threads dedicated to CPU AV1 encoding. Default: {DEFAULT_CPU_USAGE_PERCENT}% of available logical CPUs.",
        rich_help_panel="Performance",
    ),
    prompt_av1: bool = typer.Option(
        False,
        "--prompt-av1",
        help="Ask before re-encoding files that are already AV1. Default: skip already-AV1 files unless --reencode-av1 is provided.",
        rich_help_panel="File Handling",
    ),
    reencode_av1: bool = typer.Option(
        False,
        "--reencode-av1",
        help="Always re-encode files that are already AV1 without prompting. Default: do not re-encode already-AV1 files.",
        rich_help_panel="File Handling",
    ),
    probe_only: bool = typer.Option(
        False,
        "--probe-only",
        "--probe",
        help="Only inspect input files and print codec, resolution, bitrate, fps, and duration. Default: convert files instead of probe-only mode.",
        rich_help_panel="Input/Output",
    ),
    no_color: bool = typer.Option(False, "--no-color", help="Disable ANSI/Rich colors. Default: colorized terminal output is enabled.", rich_help_panel="Display"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Disable interactive confirmations. Default: prompts use their safe fallback behavior, which is usually 'No' unless another explicit flag such as --delete-original or --reencode-av1 was provided.", rich_help_panel="Display"),
    hide_filenames: bool = typer.Option(False, "--hide-filenames", help="Redact media filenames in progress output, prompts, and status messages. Default: show real filenames and relative paths.", rich_help_panel="Display"),
    parallel: int = typer.Option(1, "--parallel", "-j", help="Requested file concurrency. Default: 1. Values above 1 are accepted for future compatibility but currently run sequentially.", rich_help_panel="Performance"),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
        is_flag=True,
    ),
):
    """Universal Video Compressor (AMD/NVIDIA/CPU). Default bitrate logic reduces size when the source is high-bitrate.

        \b
        [bold cyan]EXAMPLES[/]:
            [yellow]Convert all videos in a folder[/]:
                $ av1 "C:\\Videos"
    
            [yellow]Convert single file and delete original[/]:
                $ av1 "C:\\Videos\\movie.mp4" --delete-original

            [yellow]Force in-place replacement (delete + auto-rename)[/]:
                $ av1 "C:\\Videos\\movie.mp4" --force
    
            [yellow]Wildcard pattern matching[/]:
                $ av1 "episode_*.mkv"
    
            [yellow]Batch with custom output folder[/]:
                $ av1 "C:\\Input" "C:\\Output" --overwrite
    
            [yellow]Recursive with HTML logging[/]:
                $ av1 "C:\\Videos" --recursive --log-type html
    
            [yellow]Preview what would be converted[/]:
                $ av1 "C:\\Videos" --recursive --dry-run

            [yellow]Probe files without converting[/]:
                $ av1 "C:\\Videos\\movie.mp4" --probe

            [yellow]Run the script directly and probe one file[/]:
                $ python "Python/av1/av1.py" "C:\\Videos\\movie.mp4" --probe

            [yellow]Cap output around 10 MB[/]:
                $ av1 "C:\\Videos\\clip.mp4" --max-output-size 10M

            [yellow]Aim for at least 70%% smaller file than the source[/]:
                $ av1 "C:\\Videos\\big.mkv" --min-shrink 70

            [yellow]Use a balanced preset for quick compression[/]:
                $ av1 "C:\\Videos\\movie.mp4" --size-preset balanced

            [yellow]Preset + explicit width override[/]:
                $ av1 "C:\\Videos" --size-preset aggressive --max-width 720

            [yellow]Remove stale temp files (same as `av1 clean`)[/]:
                $ av1 --clean "C:\\Videos" -r
    """
    # If version flag triggered, callback already exited.

    global _NO_COLOR, _NO_PROMPT, _HIDE_FILENAMES, console, FFMPEG_CMD, FFPROBE_CMD

    if clean_stale:
        incompatible: list[str] = []
        if probe_only:
            incompatible.append("--probe / --probe-only")
        if dry_run:
            incompatible.append("--dry-run")
        if output_dir is not None:
            incompatible.append("--output-dir")
        if bitrate is not None:
            incompatible.append("--bitrate")
        if max_output_size is not None:
            incompatible.append("--max-output-size / -S")
        if min_shrink is not None:
            incompatible.append("--min-shrink")
        if size_preset is not None:
            incompatible.append("--size-preset")
        if max_width is not None:
            incompatible.append("--max-width")
        if force:
            incompatible.append("--force / -f")
        if delete_original:
            incompatible.append("--delete-original / -d")
        if rename_original:
            incompatible.append("--rename-original / -R")
        if overwrite:
            incompatible.append("--overwrite / -o")
        if keep_mkv:
            incompatible.append("--keep-mkv")
        if log_type != "txt":
            incompatible.append("--log-type")
        if log_dir is not None:
            incompatible.append("--log-dir")
        if ffmpeg is not None:
            incompatible.append("--ffmpeg")
        if ffprobe is not None:
            incompatible.append("--ffprobe")
        if prompt_av1:
            incompatible.append("--prompt-av1")
        if reencode_av1:
            incompatible.append("--reencode-av1")
        if parallel != 1:
            incompatible.append("--parallel / -j")
        if cpu_threads is not None:
            incompatible.append("--cpu-threads / --cpu-cores")
        if incompatible:
            cprint(
                f"--clean/--cleanup cannot be combined with: {', '.join(incompatible)}",
                "error",
            )
            raise typer.Exit(code=1)

    # Apply environment overrides for color and logging
    env_no_color = os.getenv("AV1_NO_COLOR")
    if env_no_color and _env_bool(env_no_color):
        no_color = True
    env_no_prompt = os.getenv("AV1_NO_PROMPT")
    if env_no_prompt and _env_bool(env_no_prompt):
        no_prompt = True
    env_hide_filenames = os.getenv("AV1_HIDE_FILENAMES")
    if env_hide_filenames and _env_bool(env_hide_filenames):
        hide_filenames = True

    if clean_stale:
        _NO_COLOR = no_color
        _NO_PROMPT = no_prompt
        _HIDE_FILENAMES = hide_filenames
        if no_color:
            console = Console(no_color=True, force_terminal=True)
        _run_cleanup_command(input_paths, recursive=recursive)
        raise typer.Exit(code=0)

    env_cpu_threads = os.getenv("AV1_CPU_THREADS")
    if cpu_threads is None and env_cpu_threads:
        try:
            cpu_threads = int(env_cpu_threads.strip())
        except ValueError:
            cprint(f"Invalid AV1_CPU_THREADS: {env_cpu_threads!r}", "error")
            raise typer.Exit(code=1)

    env_log_type = os.getenv("AV1_LOG_TYPE")
    if env_log_type and (log_type == "txt"):
        log_type = env_log_type

    env_log_dir = os.getenv("AV1_LOG_DIR")
    if env_log_dir and log_dir is None:
        log_dir = env_log_dir

    max_output_bytes: Optional[int] = None
    resolved_size_preset, size_preset_values = _resolve_size_preset(size_preset)
    if size_preset_values:
        if min_shrink is None and isinstance(size_preset_values.get("min_shrink_percent"), (int, float)):
            min_shrink = float(size_preset_values["min_shrink_percent"])
        if max_width is None and isinstance(size_preset_values.get("max_video_width"), int):
            max_width = int(size_preset_values["max_video_width"])

    if max_output_size:
        max_output_bytes = _parse_byte_size(max_output_size)
        if not max_output_bytes or max_output_bytes <= 0:
            cprint(f"Invalid --max-output-size: {max_output_size!r} (examples: 10M, 500MB)", "error")
            raise typer.Exit(code=1)
    elif os.getenv("AV1_MAX_OUTPUT_SIZE"):
        env_spec = os.getenv("AV1_MAX_OUTPUT_SIZE", "").strip()
        max_output_bytes = _parse_byte_size(env_spec)
        if not max_output_bytes or max_output_bytes <= 0:
            cprint(f"Invalid AV1_MAX_OUTPUT_SIZE: {env_spec!r}", "error")
            raise typer.Exit(code=1)

    min_shrink_percent: Optional[float] = min_shrink
    if min_shrink_percent is None and os.getenv("AV1_MIN_SHRINK"):
        try:
            min_shrink_percent = float(os.getenv("AV1_MIN_SHRINK", "").strip())
        except ValueError:
            cprint(f"Invalid AV1_MIN_SHRINK: {os.getenv('AV1_MIN_SHRINK')!r}", "error")
            raise typer.Exit(code=1)
    if min_shrink_percent is None:
        min_shrink_percent = 50.0
    if min_shrink_percent is not None and (min_shrink_percent <= 0 or min_shrink_percent >= 100):
        cprint("--min-shrink / AV1_MIN_SHRINK must be strictly between 0 and 100.", "error")
        raise typer.Exit(code=1)
    if force:
        delete_original = True
        rename_original = True
    if keep_mkv and rename_original:
        cprint("--rename-original/--force cannot be combined with --keep-mkv.", "error")
        raise typer.Exit(code=1)
    effective_max_video_width = MAX_VIDEO_WIDTH
    if max_width is not None:
        if max_width < 64:
            cprint("--max-width must be at least 64.", "error")
            raise typer.Exit(code=1)
        effective_max_video_width = int(max_width)
    if prompt_av1 and reencode_av1:
        cprint("--prompt-av1 and --reencode-av1 are mutually exclusive.", "error")
        raise typer.Exit(code=1)
    if cpu_threads is not None and cpu_threads < 1:
        cprint("--cpu-threads / --cpu-cores / AV1_CPU_THREADS must be at least 1.", "error")
        raise typer.Exit(code=1)
    available_cpu_threads = _logical_cpu_count()
    if cpu_threads is not None and cpu_threads > available_cpu_threads:
        cprint(
            f"--cpu-threads / --cpu-cores / AV1_CPU_THREADS cannot exceed available logical CPUs "
            f"({available_cpu_threads}).",
            "error",
        )
        raise typer.Exit(code=1)

    effective_cpu_threads = _resolve_cpu_threads(cpu_threads)

    # Override ffmpeg/ffprobe paths from CLI if provided
    if ffmpeg:
        FFMPEG_CMD = ffmpeg
    if ffprobe:
        FFPROBE_CMD = ffprobe
    
    # Validate parallel value
    requested_parallel = parallel
    if parallel < 1:
        cprint("⚠️  --parallel must be at least 1, setting to 1", "warning")
        parallel = 1
    elif parallel > 1:
        cprint(f"⚠️  --parallel {parallel} requested, but this build currently runs sequentially.", "warning")
        cprint("    Using --parallel 1 for now.", "info")
        parallel = 1

    # Set global no-color flag and reinitialize console
    _NO_COLOR = no_color
    _NO_PROMPT = no_prompt
    _HIDE_FILENAMES = hide_filenames
    if no_color:
        console = Console(no_color=True, force_terminal=True)
    
    if not input_paths:
        # Show main command help (group-level --help lists subcommands only).
        app(["main", "--help"])
        raise typer.Exit(code=0)

    _print_startup_summary(
        input_paths,
        output_dir=output_dir,
        bitrate=bitrate,
        max_output_size=max_output_size,
        min_shrink_percent=min_shrink_percent,
        force=force,
        delete_original=delete_original,
        rename_original=rename_original,
        overwrite=overwrite,
        dry_run=dry_run,
        recursive=recursive,
        keep_mkv=keep_mkv,
        log_type=log_type,
        log_dir=log_dir,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
        no_color=no_color,
        no_prompt=no_prompt,
        hide_filenames=hide_filenames,
        prompt_av1=prompt_av1,
        reencode_av1=reencode_av1,
        probe_only=probe_only,
        cpu_threads_requested=cpu_threads,
        effective_cpu_threads=effective_cpu_threads,
        requested_parallel=requested_parallel,
        effective_parallel=parallel,
        size_preset=resolved_size_preset,
        max_video_width=effective_max_video_width,
    )

    if probe_only:
        _confirm_root_like_input_paths(input_paths, intent="probe", recursive=recursive)
        check_ffprobe()
        probe_inputs(input_paths, recursive=recursive)
    else:
        _confirm_root_like_input_paths(input_paths, intent="convert", recursive=recursive)
        check_ffmpeg()

        global _AUTO_REENCODE_AV1, _AUTO_OVERWRITE_EXISTING, _AUTO_RENAME_TO_ORIGINAL
        _AUTO_REENCODE_AV1 = False
        _AUTO_OVERWRITE_EXISTING = False
        _AUTO_RENAME_TO_ORIGINAL = bool(rename_original)

        has_patterns = any("*" in input_path or "?" in input_path for input_path in input_paths)
        if len(input_paths) > 1 or has_patterns:
            matched_files = _resolve_video_input_files(input_paths, recursive=recursive)
            if not matched_files:
                cprint("❌ No video files found in arguments.", "error")
                raise typer.Exit(code=1)

            cprint(f"Found {len(matched_files)} file(s) to process.", "info")
            base_path = _resolve_batch_base_path(matched_files)

            process_batch_files(
                matched_files,
                output_dir,
                base_path,
                bitrate,
                delete_original,
                overwrite,
                dry_run,
                keep_mkv,
                recursive=recursive,
                transient_progress=False,
                cpu_threads=effective_cpu_threads,
                prompt_av1=prompt_av1,
                reencode_av1=reencode_av1,
                max_output_bytes=max_output_bytes,
                min_shrink_percent=min_shrink_percent,
                max_video_width=effective_max_video_width,
            )
        else:
            input_path = input_paths[0]
            convert_videos(
                input_path,
                output_dir,
                bitrate,
                delete_original,
                overwrite,
                dry_run,
                recursive,
                keep_mkv,
                cpu_threads=effective_cpu_threads,
                prompt_av1=prompt_av1,
                reencode_av1=reencode_av1,
                max_output_bytes=max_output_bytes,
                min_shrink_percent=min_shrink_percent,
                max_video_width=effective_max_video_width,
            )
    
    # Save logs only if files were actually converted
    global _LOG_MESSAGES
    if _LOG_MESSAGES and not probe_only:
        import tempfile
        resolved_log_dir = log_dir
        if resolved_log_dir is None:
            temp_base = tempfile.gettempdir()
            resolved_log_dir = os.path.join(temp_base, "av1-logs")
        _save_log(log_type, resolved_log_dir)

if __name__ == "__main__":
    try:
        sys.argv[:] = _normalize_cli_argv(sys.argv)
        app()
    finally:
        # Best-effort terminal restore: show cursor and reset terminal state.
        try:
            console.show_cursor()
        except Exception:
            pass
        try:
            # Ensure echo/icanon etc. are restored for shells that lost input visibility
            # Only invoke `stty` if it's present on the system (Windows typically lacks it).
            import shutil
            if shutil.which("stty"):
                os.system("stty sane")
        except Exception:
            pass