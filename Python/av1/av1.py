# ============================================================================ #
#                                     av1.py                                   #
# ============================================================================ #
# usage (cross-platform):
# av1 "/path/to/videos" "/path/to/output"  (Linux/Mac)
# av1 "C:\\Videos\\Input" "C:\\Videos\\Output"  (Windows)
# av1 "video.mp4" --delete-original
# av1 "/path/to/videos" -r  (recursive)

import os
import subprocess
import shutil
import sys
import json
import platform
import glob
import time
import signal
from datetime import datetime, UTC
from typing import Optional, Tuple

# Force UTF-8 encoding on Windows
if platform.system() == 'Windows':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
import typer

# ============================================================================ #
#                           APP & CLI CONFIGURATION                            #
# ============================================================================ #
__app_name__ = "av1"
__version__ = "0.3.1"

console = Console()  # Will be reinitialized in main() if --no-color is set
app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    rich_markup_mode="rich",  # Enable Rich markup in help output
)

# ============================================================================ #
#                        ENCODING CONFIGURATION CONSTANTS                      #
# ============================================================================ #
BITRATE_REDUCTION_FACTOR = 0.5
BITRATE_FALLBACK = 2_000_000
BITRATE_MAXRATE_MULTIPLIER = 1.2
BITRATE_BUFSIZE_MULTIPLIER = 2.0

# ============================================================================ #
#                         FILE HANDLING CONSTANTS                              #
# ============================================================================ #
SUPPORTED_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".webm")
MIN_FILE_SIZE_BYTES = 1024  # Skip files smaller than 1KB
DISK_SPACE_SAFETY_MARGIN = 1.5  # Require 1.5x file size in free space

# ============================================================================ #
#                        ENCODING PARAMETER CONSTANTS                          #
# ============================================================================ #
AUDIO_BITRATE = "64k"  # Opus audio bitrate per stream
MAX_VIDEO_WIDTH = 1920  # Maximum video width (maintains aspect ratio)
VIDEO_BITRATE_ESTIMATE_FACTOR = 0.9  # Factor to estimate video-only bitrate from total
PROGRESS_TIMEOUT = 10  # Timeout for ffprobe operations (seconds)
ENCODER_TEST_TIMEOUT = 5  # Timeout for encoder detection tests (seconds)

# ============================================================================ #
#                           ENVIRONMENT OVERRIDES                             #
# ============================================================================ #
# Environment variables to tweak behavior without changing CLI:
#   AV1_AUDIO_BITRATE, AV1_MAX_VIDEO_WIDTH, AV1_BITRATE_REDUCTION_FACTOR,
#   AV1_BITRATE_FALLBACK, AV1_NO_COLOR, AV1_LOG_TYPE, AV1_LOG_DIR,
#   AV1_FFMPEG_PATH, AV1_FFPROBE_PATH

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

# ============================================================================ #
#                          VERSION FLAG CALLBACK                               #
# ============================================================================ #
def _version_callback(value: bool) -> None:
    """Display version and exit."""
    if value:
        typer.echo(f"{__app_name__} {__version__}")
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
    
    NOTES:
      • Logs saved to ./logs/ by default
      • Press Ctrl+C once to finish current file and exit gracefully
      • Use -h or --help for complete option list
    """
    console.print(examples)


def _format_saved(bytes_amount: float) -> str:
    """Pretty-print saved bytes as KB/MB/GB for progress columns."""
    if bytes_amount >= 1024 ** 3:
        return f"{bytes_amount / (1024 ** 3):.2f} GB"
    if bytes_amount >= 1024 ** 2:
        return f"{bytes_amount / (1024 ** 2):.1f} MB"
    if bytes_amount >= 1024:
        return f"{bytes_amount / 1024:.1f} KB"
    return "0"

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
def cprint(message: str, type: str = "", style: str = "bold green", **kwargs) -> None:
    prefix = ""
    style  = ""
    type   = type.lower()

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

    message = f"{prefix}  {message}"
    
    # Disable styling if _NO_COLOR is set; respect suppression for console output only
    if not _SUPPRESS_OUTPUT:
        if _NO_COLOR:
            console.print(message, **kwargs)
        else:
            console.print(message, style=style, **kwargs)
    
    # Log the message (with prefix for file logging) and structured event
    _LOG_MESSAGES.append(message)
    try:
        _LOG_EVENTS.append({
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "level": type or "info",
            "message": message,
        })
    except Exception:
        pass

# ============================================================================ #
#                            FUNCTION: safe_input                              #
# ============================================================================ #
def safe_input(prompt: str) -> str:
    """
    Input function that pauses progress bar if active.
    """
    global _PROGRESS_CONTEXT
    if _PROGRESS_CONTEXT:
        _PROGRESS_CONTEXT.stop()
    result = input(prompt)
    if _PROGRESS_CONTEXT:
        _PROGRESS_CONTEXT.start()
    return result

# ============================================================================ #
#                      FUNCTION: get_input_bitrate                             #
# ============================================================================ #
def get_input_bitrate(file_path: str) -> Optional[int]:
    """
    Returns the bitrate of the video stream in bits/s.
    Falls back to calculating from file size and duration if not available.
    """
    try:
        cmd = [
            FFPROBE_CMD, "-v", "error", 
            "-select_streams", "v:0",
            "-show_entries", "stream=bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=1", 
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=PROGRESS_TIMEOUT)
        val = result.stdout.strip()
        if val.isdigit():
            return int(val)
        
        # Fallback: Calculate from duration/size
        cmd_dur = [
            FFPROBE_CMD, "-v", "error", 
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", 
            file_path
        ]
        result_dur = subprocess.run(cmd_dur, capture_output=True, text=True, timeout=10)
        duration_str = result_dur.stdout.strip()
        
        if duration_str and duration_str.replace('.', '', 1).isdigit():
            duration = float(duration_str)
            size = os.path.getsize(file_path)
            
            if duration > 0:
                # Calculate total bitrate, apply factor to estimate video-only bitrate
                return int((size * 8 / duration) * VIDEO_BITRATE_ESTIMATE_FACTOR)
            
    except subprocess.TimeoutExpired:
        cprint(f"Timeout while probing file: {os.path.basename(file_path)}", "warning")
    except Exception as e:
        cprint(f"Could not calculate input bitrate: {e}", "warning")
    
    return None

# ============================================================================ #
#                       FUNCTION: check_encoder_support                        #
# ============================================================================ #
def check_encoder_support(encoder_name: str) -> bool:
    """
    Checks if a specific FFmpeg encoder is usable (drivers installed).
    Uses 720p test to satisfy RDNA3 and newer NVENC requirements.
    """
    try:
        # Use 720p test to satisfy RDNA3 and newer NVENC requirements
        cmd = [
            FFMPEG_CMD, "-v", "quiet", "-f", "lavfi",
            "-i", "testsrc=size=1280x720:rate=30:duration=0.1",
            "-c:v", encoder_name, "-f", "null", "-"
        ]
        return subprocess.run(cmd, check=False, timeout=ENCODER_TEST_TIMEOUT).returncode == 0
    except Exception:
        return False

# ============================================================================ #
#                            FUNCTION: check_ffmpeg                            #
# ============================================================================ #
def check_ffmpeg() -> None:
    global ACTIVE_ENCODER, FFMPEG_CMD, FFPROBE_CMD
    # Validate ffmpeg path or fallback to PATH
    ffmpeg_ok = shutil.which(FFMPEG_CMD) or (os.path.exists(FFMPEG_CMD) and os.path.isfile(FFMPEG_CMD))
    if not ffmpeg_ok:
        path_ffmpeg = shutil.which("ffmpeg")
        if path_ffmpeg:
            FFMPEG_CMD = path_ffmpeg
        else:
            cprint("ffmpeg is not found.", "error")
            raise typer.Exit(code=1)
    # Validate ffprobe path or fallback to PATH
    ffprobe_ok = shutil.which(FFPROBE_CMD) or (os.path.exists(FFPROBE_CMD) and os.path.isfile(FFPROBE_CMD))
    if not ffprobe_ok:
        path_ffprobe = shutil.which("ffprobe")
        if path_ffprobe:
            FFPROBE_CMD = path_ffprobe
        else:
            cprint("ffprobe is not found.", "error")
            raise typer.Exit(code=1)
    
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

# ============================================================================ #
#                          FUNCTION: needs_transcoding                         #
# ============================================================================ #
def needs_transcoding(file_path: str) -> bool:
    """
    Determines if a video file needs transcoding based on current codec.
    Returns True if transcoding is needed, False otherwise.
    """
    try:
        cmd = [FFPROBE_CMD, "-v", "quiet", "-print_format", "json", "-show_streams", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=PROGRESS_TIMEOUT)
        
        if result.returncode != 0:
            cprint(f"Warning: Could not probe {os.path.basename(file_path)}", "warning")
            return False
            
        data = json.loads(result.stdout)
        target_codec = ACTIVE_ENCODER["codec"]

        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                current_codec = stream.get('codec_name')
                
                # Logic: If we are targeting AV1, skip if already AV1.
                # If targeting HEVC, skip if already HEVC (or AV1, which is better).
                if target_codec == "av1" and current_codec == "av1": 
                    return False
                if target_codec == "hevc" and current_codec in ['hevc', 'h265', 'av1']: 
                    return False
                
                return True # Needs update
        return False
    except subprocess.TimeoutExpired:
        cprint(f"Timeout while probing {os.path.basename(file_path)}", "warning")
        return False
    except json.JSONDecodeError:
        cprint(f"Invalid video file: {os.path.basename(file_path)}", "warning")
        return False
    except Exception as e:
        cprint(f"Error checking file: {e}", "warning")
        return False

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
            cprint(f"Deleted original: {os.path.basename(original_path)}")
            return True
        # Suppress interactive prompt when _NO_PROMPT is enabled
        if _NO_PROMPT:
            return False
        resp = safe_input(f"Delete original file?\n{original_path}\n[y/N/a]: ").strip().lower()
        if resp in ("y", "yes"):
            os.remove(original_path)
            cprint("Original deleted.", "success")
            return False
        elif resp in ("a", "all"):
            os.remove(original_path)
            cprint("Original deleted.", "success")
            return True
    except PermissionError:
        cprint(f"Permission denied: Cannot delete {original_path}", "error")
    except Exception as e:
        cprint(f"Could not delete {original_path}: {e}", "warning")
    return False

# ============================================================================ #
#                        FUNCTION: check_disk_space                            #
# ============================================================================ #
def check_disk_space(file_path: str, output_dir: str) -> bool:
    """
    Verifies sufficient disk space is available for conversion.
    Returns True if enough space, False otherwise.
    """
    try:
        file_size = os.path.getsize(file_path)
        required_space = int(file_size * DISK_SPACE_SAFETY_MARGIN)
        
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
def validate_video_file(file_path: str) -> bool:
    """
    Validates that a file is a supported video file.
    Returns True if valid, False otherwise.
    """
    if not os.path.isfile(file_path):
        return False
        
    if not file_path.lower().endswith(SUPPORTED_EXTENSIONS):
        return False
    
    # Check minimum file size
    try:
        if os.path.getsize(file_path) < MIN_FILE_SIZE_BYTES:
            cprint(f"File too small: {os.path.basename(file_path)}", "warning")
            return False
    except OSError:
        return False
        
    return True

# ============================================================================ #
#                         FUNCTION: convert_single_file                        #
# ============================================================================ #
def convert_single_file(input_path: str, output_dir: Optional[str] = None, 
                       bitrate: Optional[str] = None, delete_original: bool = False, 
                       overwrite: bool = False, dry_run: bool = False, keep_mkv: bool = False, show_progress: bool = True) -> Tuple[bool, int]:
    """
    Converts a single video file to the target codec.
    Returns a tuple: (auto_delete_flag, size_saved_bytes)
    - auto_delete_flag: True if user selected 'all' for auto-delete
    - size_saved_bytes: Bytes saved (positive) or added (negative), 0 if skipped/failed
    """
    filename = os.path.basename(input_path)
    

    # Validate file
    if not validate_video_file(input_path):
        return delete_original, 0

    if not needs_transcoding(input_path):
        cprint(f"⏭️  Skipping: {filename} (already using target codec)", "info")
        return delete_original, 0

    # Show actual file size before conversion (only if not suppressed)
    if not _SUPPRESS_OUTPUT:
        try:
            file_size_bytes = os.path.getsize(input_path)
            file_size_mb = file_size_bytes / (1024 ** 2)
            cprint(f"📦 Input size: {file_size_mb:.2f} MB", "info")
        except Exception as e:
            cprint(f"Could not determine file size: {e}", "warning")

    # Naming suffix - keep original name if deleting source, otherwise add codec suffix
    if output_dir is None:
        output_dir = os.path.dirname(input_path)
        # When staying in same dir, add suffix to avoid collision during encoding
        suffix = f"-{ACTIVE_ENCODER['codec'].upper()}.mkv"
        output_name = os.path.splitext(filename)[0] + suffix
    else:
        os.makedirs(output_dir, exist_ok=True)
        suffix = f"-{ACTIVE_ENCODER['codec'].upper()}.mkv"
        output_name = os.path.splitext(filename)[0] + suffix
    
    output_path = os.path.join(output_dir, output_name)
    temp_output = f"{output_path}.temp.mkv"
    
    # Check disk space before proceeding (skip in dry run)
    if not dry_run:
        if not check_disk_space(input_path, output_dir):
            return delete_original, 0

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        if not overwrite:
            if safe_input(f"File exists: {output_path}. Delete? [y/N]: ").lower() not in ("y", "yes"):
                return delete_original, 0

    # --- CALCULATE TARGET BITRATE ---
    target_bitrate_int = 0
    if bitrate:
        try:
            if isinstance(bitrate, str) and bitrate.lower().endswith('m'):
                target_bitrate_int = int(float(bitrate[:-1]) * 1_000_000)
            elif isinstance(bitrate, str) and bitrate.lower().endswith('k'):
                target_bitrate_int = int(float(bitrate[:-1]) * 1_000)
            else:
                target_bitrate_int = int(bitrate)
        except ValueError:
            cprint(f"Invalid bitrate format: {bitrate}. Using auto-detection.", "warning")
            bitrate = None
    
    if not bitrate:
        input_bitrate = get_input_bitrate(input_path)
        if input_bitrate:
            target_bitrate_int = int(input_bitrate * BITRATE_REDUCTION_FACTOR)
            if not _SUPPRESS_OUTPUT:
                cprint(f"🎯 Bitrate: {input_bitrate/1_000_000:.2f}M → {target_bitrate_int/1_000_000:.2f}M ({int(BITRATE_REDUCTION_FACTOR*100)}% reduction)", "info")
        else:
            if not _SUPPRESS_OUTPUT:
                cprint(f"⚠️  Bitrate unknown, using {BITRATE_FALLBACK/1_000_000:.1f}M fallback", "warning")
            target_bitrate_int = BITRATE_FALLBACK

    # --- BUILD COMMAND ---
    # Pixel format selection: CPU uses yuv420p, GPU encoders typically use nv12, VAAPI uses same
    if ACTIVE_ENCODER["hw_type"] == "cpu":
        pix_fmt = "yuv420p"
    elif ACTIVE_ENCODER["hw_type"] == "vaapi":
        pix_fmt = "nv12"  # VAAPI encoder input format
    else:
        pix_fmt = "nv12"  # NVIDIA/AMD default
    
    command = [
        FFMPEG_CMD, "-y", "-i", input_path,
        "-vf", f"scale='min({MAX_VIDEO_WIDTH},iw)':-2:force_original_aspect_ratio=decrease,format={pix_fmt}",
        "-movflags", "+faststart",
    ]

    # --- ENCODER SPECIFIC SETTINGS ---
    encoder_name = ACTIVE_ENCODER["encoder"]
    hw_type = ACTIVE_ENCODER["hw_type"]
    codec = ACTIVE_ENCODER["codec"]

    command.extend(["-c:v", encoder_name])

    # Universal Metadata
    command.extend(["-metadata", "major_brand=mp42", "-metadata", "compatible_brands=mp42av01iso2mp41"])
    if codec == "hevc":
        command.extend(["-tag:v", "hvc1"])

    # Rate Control: 50% Reduction Strategy (VBR)
    # We use typical flags: -b:v (target), -maxrate (peak), -bufsize
    bitrate_args = [
        "-b:v", str(target_bitrate_int),
        "-maxrate", str(int(target_bitrate_int * BITRATE_MAXRATE_MULTIPLIER)),
        "-bufsize", str(int(target_bitrate_int * BITRATE_BUFSIZE_MULTIPLIER))
    ]

    # Apply Vendor Specific Flags
    if hw_type == "nvidia":
        # NVIDIA (NVENC)
        # -preset p7: Slowest/Best Quality (Hardware is fast enough to afford this)
        # -rc vbr: Explicitly set VBR mode
        command.extend(["-preset", "p7", "-rc", "vbr"])
        command.extend(bitrate_args)
        
    elif hw_type == "amd":
        # AMD (AMF)
        # -usage transcoding: Optimization for transcoding workloads
        # -quality balanced: AMF defaults
        command.extend(["-usage", "transcoding", "-quality", "balanced", "-profile:v", "main"])
        command.extend(bitrate_args)
        
    else:
        # CPU (SVT-AV1)
        command.extend(["-preset", "8", "-g", "240"])
        command.extend(bitrate_args)

    # Audio: Copy or convert to Opus
    # Preserve multi-channel audio if present, otherwise use stereo
    command.extend(["-c:a", "libopus", "-b:a", AUDIO_BITRATE, temp_output])

    if not _SUPPRESS_OUTPUT:
        cprint(f"🎬 Converting: {filename}", "info")
        cprint(f"   Encoder: {encoder_name} ({codec.upper()}, {hw_type.upper()})", "info")
    # Initialize per-file event context
    file_event = {
        "file": input_path,
        "output": output_path,
        "encoder": encoder_name,
        "codec": codec,
        "target_bps": target_bitrate_int,
    }

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
        if not _SUPPRESS_OUTPUT:
            cprint("🔍 Dry run: Planned conversion", "info")
            console.print(summary)
        try:
            _LOG_EVENTS.append({
                "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                "level": "info",
                "message": "dry_run_summary",
                "data": summary,
            })
        except Exception:
            pass
        return delete_original, 0
    
    # Get video duration for progress calculation
    try:
        duration_cmd = [FFPROBE_CMD, "-v", "error", "-show_entries", "format=duration", 
                       "-of", "default=noprint_wrappers=1:nokey=1", input_path]
        duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=PROGRESS_TIMEOUT)
        duration_str = duration_result.stdout.strip()
        total_duration = float(duration_str) if duration_str and duration_str.replace('.', '', 1).isdigit() else None
    except (subprocess.TimeoutExpired, ValueError, subprocess.SubprocessError) as e:
        cprint(f"Could not determine video duration: {e}", "warning")
        total_duration = None
    
    try:
        # Run ffmpeg with progress tracking
        import re
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                   universal_newlines=True, bufsize=1)
        
        # If we have a progress context, add a sub-task for this file
        # Only show encoding progress for single-file conversions (show_progress=True)
        file_task = None
        if _PROGRESS_CONTEXT and show_progress and total_duration and process.stdout:
            encoding_start = time.time()
            file_task = _PROGRESS_CONTEXT.add_task(
                f"[yellow]  └─ Encoding: {filename}", 
                total=100,
                fps="",
                eta="",
            )
            
            try:
                for line in process.stdout:
                    # Parse ffmpeg progress output
                    time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                    fps_match = re.search(r'fps=\s*(\d+\.?\d*)', line)
                    
                    if time_match and total_duration:
                        hours, minutes, seconds = map(float, time_match.groups())
                        current_time = hours * 3600 + minutes * 60 + seconds
                        progress_percent = min((current_time / total_duration) * 100, 100)
                        
                        # Calculate ETA
                        elapsed = time.time() - encoding_start
                        if progress_percent > 0 and elapsed > 0:
                            total_estimated = (elapsed / progress_percent) * 100
                            eta_seconds = int(total_estimated - elapsed)
                            eta_str = f"{eta_seconds // 60}m {eta_seconds % 60}s" if eta_seconds > 60 else f"{eta_seconds}s"
                        else:
                            eta_str = "calculating..."
                        
                        # Get FPS info
                        fps_str = f"{int(float(fps_match.group(1)))} fps" if fps_match else ""
                        
                        _PROGRESS_CONTEXT.update(
                            file_task, 
                            completed=progress_percent,
                            fps=fps_str,
                            eta=f"ETA: {eta_str}"
                        )
                
                process.wait()
                _PROGRESS_CONTEXT.update(file_task, completed=100, eta="Done")
            finally:
                if file_task is not None:
                    _PROGRESS_CONTEXT.remove_task(file_task)
                    
        elif _PROGRESS_CONTEXT and show_progress and process.stdout:
            # No duration available; show a spinner-like indeterminate bar
            file_task = _PROGRESS_CONTEXT.add_task(
                f"[yellow]  └─ Encoding: {filename}", 
                total=None,
                saved="",
            )
            try:
                for _ in process.stdout:
                    pass
                process.wait()
            finally:
                if file_task is not None:
                    _PROGRESS_CONTEXT.remove_task(file_task)
        else:
            # No progress context, just consume output
            if process.stdout:
                for line in process.stdout:
                    pass
            process.wait()
        
        result = process
    except Exception as e:
        cprint(f"FFmpeg execution error: {e}", "error")
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except OSError:
                pass
        return delete_original, 0

    if result.returncode == 0:
        try:
            if os.path.exists(temp_output) and os.path.getsize(temp_output) > MIN_FILE_SIZE_BYTES:
                os.replace(temp_output, output_path)
                file_size = os.path.getsize(input_path)
                new_file_size = os.path.getsize(output_path)
                size_saved = file_size - new_file_size
                saved_percent = (size_saved / file_size) * 100 if file_size > 0 else 0
                if not _SUPPRESS_OUTPUT:
                    cprint(f"✅ Complete: {file_size / (1024**2):.2f} MB → {new_file_size / (1024**2):.2f} MB", "success")
                    cprint(f"   💾 Saved: {size_saved / (1024**2):.2f} MB ({saved_percent:.1f}%)", "success")
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
                    if not _SUPPRESS_OUTPUT:
                        cprint("⚠️  Warning: Output file is larger than input (entropy/quality issue)", "warning")
                    # Still offer to delete if user wants
                    auto_delete_flag = maybe_delete_original(input_path, auto_delete=delete_original)
                    # Track if original was deleted in this step
                    original_deleted = not os.path.exists(input_path)
                    if auto_delete_flag:
                        delete_original = True
                    # If original was deleted, rename output to original name when same directory
                    if original_deleted and os.path.dirname(output_path) == os.path.dirname(input_path) and not keep_mkv:
                        original_name_path = input_path
                        if output_path != original_name_path:
                            try:
                                os.rename(output_path, original_name_path)
                                cprint(f"Renamed to: {os.path.basename(original_name_path)}", "success")
                            except OSError as e:
                                cprint(f"Could not rename to original name: {e}", "warning")
                else:
                    # Delete original and optionally rename to match original name
                    auto_delete_flag = maybe_delete_original(input_path, auto_delete=delete_original)
                    # Track if original was deleted in this step
                    original_deleted = not os.path.exists(input_path)
                    if auto_delete_flag:
                        delete_original = True
                    
                    # Rename converted file to original name if original was deleted (unless keep_mkv is set)
                    if original_deleted and os.path.dirname(output_path) == os.path.dirname(input_path) and not keep_mkv:
                        original_name_path = input_path
                        if output_path != original_name_path:
                            try:
                                os.rename(output_path, original_name_path)
                                cprint(f"Renamed to: {os.path.basename(original_name_path)}", "success")
                            except OSError as e:
                                cprint(f"Could not rename to original name: {e}", "warning")
                
                return delete_original, size_saved
            else:
                cprint("❌ Error: Temp file missing or invalid!", "error")
        except OSError as e:
            cprint(f"❌ Error swapping files: {e}", "error")
    else:
        cprint(f"❌ Conversion failed (exit code: {result.returncode})", "error")
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except Exception as e:
                cprint(f"Could not remove temp file: {e}", "warning")

    return delete_original, 0

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
    transient_progress: bool = True
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
    
    # Track statistics for batch summary
    total_original_size = 0
    total_new_size = 0
    files_converted = 0
    per_file_stats: list[Tuple[str, int, int, float]] = []
    cumulative_saved = 0
    batch_start_time = time.time()
    file_times: list[float] = []
    
    # Set up graceful cancellation handler
    global _USER_CANCELLED
    _USER_CANCELLED = False
    signal.signal(signal.SIGINT, _signal_handler)
    
    # Process files with progress tracking
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[cyan]{task.fields[fps]}"),
        TextColumn("[yellow]{task.fields[eta]}"),
        TextColumn("[green]Saved: {task.fields[saved]}"),
        transient=transient_progress,
    ) as progress:
        global _PROGRESS_CONTEXT
        _PROGRESS_CONTEXT = progress
        
        overall_task = progress.add_task(
            f"[cyan]Converting 0/{len(video_files)} files...",
            total=len(video_files),
            saved=_format_saved(0),
            fps="",
            eta="",
        )
        
        auto_delete = delete_original
        
        for idx, file_path in enumerate(video_files, 1):
            # Check if user cancelled
            if _USER_CANCELLED:
                cprint("\n⏸️  Batch conversion interrupted. Finishing current file...", "warning")
                break
            
            # Show relative path for recursive mode
            display_path = os.path.relpath(file_path, input_path) if recursive else os.path.basename(file_path)
            file_start = time.time()
            elapsed = int(time.time() - batch_start_time)
            progress.update(overall_task, description=f"[cyan]Converting {idx}/{len(video_files)} files... ({elapsed}s) → {display_path}")
            
            # Capture original size before conversion
            try:
                original_size = os.path.getsize(file_path)
            except OSError:
                original_size = 0
            
            # Determine output directory
            if output_dir and output_dir != input_path:
                # User provided explicit output directory - preserve folder structure
                rel_dir = os.path.dirname(os.path.relpath(file_path, input_path))
                current_output_dir = os.path.join(output_dir, rel_dir) if rel_dir else output_dir
            else:
                # No explicit output dir or same as input - use file's own directory
                current_output_dir = os.path.dirname(file_path)
            
            # Suppress output during conversion
            global _SUPPRESS_OUTPUT
            _SUPPRESS_OUTPUT = True
            auto_delete_result, size_saved = convert_single_file(
                file_path, current_output_dir, bitrate, auto_delete, overwrite, dry_run, keep_mkv, show_progress=True
            )
            _SUPPRESS_OUTPUT = False
            
            # Track statistics if conversion happened
            if size_saved != 0:
                files_converted += 1
                total_original_size += original_size
                total_new_size += (original_size - size_saved)
                cumulative_saved += size_saved
                saved_percent = (size_saved / original_size * 100) if original_size > 0 else 0
                per_file_stats.append((display_path, original_size, size_saved, saved_percent))
                
                # Track file encoding time for ETA
                file_time = time.time() - file_start
                file_times.append(file_time)
            
            # Update auto-delete flag based on user's "all" choice
            if auto_delete_result:
                auto_delete = True
            
            # Update progress and show running total saved
            progress.advance(overall_task)
            elapsed = int(time.time() - batch_start_time)
            
            # Calculate ETA if we have timing data
            eta_str = ""
            if file_times:
                avg_time_per_file = sum(file_times) / len(file_times)
                remaining_files = len(video_files) - idx
                eta_seconds = int(avg_time_per_file * remaining_files)
                if eta_seconds > 0:
                    eta_str = f" | ETA: {eta_seconds}s"
            
            progress.update(
                overall_task,
                description=f"[cyan]Converting {idx}/{len(video_files)} files... ({elapsed}s{eta_str}) → {display_path}",
                fields={"saved": _format_saved(cumulative_saved), "fps": "", "eta": ""},
            )
        
        _PROGRESS_CONTEXT = None
    
    # Display batch summary
    batch_elapsed = int(time.time() - batch_start_time)
    status_msg = "interrupted" if _USER_CANCELLED else "complete"
    
    console.print(f"\n{'='*60}", style="cyan")
    cprint(f"📊 Batch conversion {status_msg}!", "success" if not _USER_CANCELLED else "warning")
    console.print(f"{'='*60}", style="cyan")
    
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
            for filename, orig_size, saved, percent in per_file_stats:
                status = "✅" if saved > 0 else "⚠️"
                cprint(f"   {status} {filename}: {saved / (1024**2):.2f} MB saved ({percent:.1f}%)", "info")
        elif per_file_stats:
            cprint("\n📋 Showing top 10 files by space saved:", style="bold cyan")
            top_files = sorted(per_file_stats, key=lambda x: x[2], reverse=True)[:10]
            for filename, orig_size, saved, percent in top_files:
                cprint(f"   ✅ {filename}: {saved / (1024**2):.2f} MB saved ({percent:.1f}%)", "info")
        
        cprint("\n💾 Total Space Savings:", style="bold cyan")
        cprint(f"   Before:  {total_original_size / (1024**3):.2f} GB", "info")
        cprint(f"   After:   {total_new_size / (1024**3):.2f} GB", "info")
        cprint(f"   Saved:   {total_saved / (1024**3):.2f} GB ({percent_saved:.1f}%)", "success")
        
        if batch_elapsed > 0:
            avg_time = batch_elapsed / files_converted
            cprint(f"   Average: {avg_time:.1f}s per file", "info")
    
    console.print(f"{'='*60}\n", style="cyan")
    
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
    keep_mkv: bool = False
) -> None:
    """
    Main entry point for converting videos.
    Handles both single files and directory processing.
    Supports recursive subdirectory traversal when recursive=True.
    """
    if os.path.isfile(input_path):
        # Single file - no batch summary needed
        convert_single_file(input_path, output_dir, bitrate, delete_original, overwrite, dry_run, keep_mkv)
    elif os.path.isdir(input_path):
        if output_dir is None:
            output_dir = input_path
        else:
            os.makedirs(output_dir, exist_ok=True)
        
        # Collect all video files (recursively or not)
        video_files = []
        
        if recursive:
            # Recursive: walk all subdirectories
            for root, dirs, files in os.walk(input_path):
                for filename in files:
                    if filename.lower().endswith(SUPPORTED_EXTENSIONS):
                        file_path = os.path.join(root, filename)
                        video_files.append(file_path)
        else:
            # Non-recursive: only current directory
            for filename in os.listdir(input_path):
                file_path = os.path.join(input_path, filename)
                if os.path.isfile(file_path) and filename.lower().endswith(SUPPORTED_EXTENSIONS):
                    video_files.append(file_path)
        
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
            video_files, output_dir, input_path, bitrate, delete_original,
            overwrite, dry_run, keep_mkv, recursive, transient_progress=True
        )
    else:
        cprint("❌ Invalid path: File or directory does not exist.", "error")

@app.command()
def main(
    input_paths: list[str] = typer.Argument(None, help="Paths to input (supports wildcards like 'test*.mp4') - see README.md for examples"),
    output_dir: Optional[str] = typer.Option(None, help="Output dir"),
    bitrate: Optional[str] = typer.Option(None, help="Override bitrate (e.g., 2500k, 2.5m)"),
    delete_original: bool = typer.Option(False, "-d", "--delete-original", help="Auto-delete originals after conversion"),
    overwrite: bool = typer.Option(False, "-o", "--overwrite", help="Overwrite existing output files"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show planned actions without converting"),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Process subdirectories recursively"),
    keep_mkv: bool = typer.Option(False, "--keep-mkv", help="Keep .mkv extension instead of matching original filename"),
    log_type: str = typer.Option("txt", "--log-type", help="Log type: 'txt', 'html', 'json', or 'none'"),
    log_dir: Optional[str] = typer.Option(None, "--log-dir", help="Directory to save logs (default: %TEMP%/av1-logs)"),
    ffmpeg: Optional[str] = typer.Option(None, "--ffmpeg", help="Path to ffmpeg executable (overrides env)"),
    ffprobe: Optional[str] = typer.Option(None, "--ffprobe", help="Path to ffprobe executable (overrides env)"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable colored output"),
    no_prompt: bool = typer.Option(False, "--no-prompt", help="Do not ask for interactive confirmations (e.g., delete original)"),
    parallel: int = typer.Option(1, "--parallel", "-j", help="Number of files to process simultaneously (GPU: 2-4 recommended, CPU: 1)"),
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
    """Universal Video Compressor (AMD/NVIDIA/CPU) - Force 50% size reduction.

        \b
        [bold cyan]EXAMPLES[/]:
            [yellow]Convert all videos in a folder[/]:
                $ av1 "C:\\Videos"
    
            [yellow]Convert single file and delete original[/]:
                $ av1 "C:\\Videos\\movie.mp4" --delete-original
    
            [yellow]Wildcard pattern matching[/]:
                $ av1 "episode_*.mkv"
    
            [yellow]Batch with custom output folder[/]:
                $ av1 "C:\\Input" "C:\\Output" --overwrite
    
            [yellow]Recursive with HTML logging[/]:
                $ av1 "C:\\Videos" --recursive --log-type html
    
            [yellow]Preview what would be converted[/]:
                $ av1 "C:\\Videos" --recursive --dry-run
    """
    # If version flag triggered, callback already exited.
    
    # Apply environment overrides for color and logging
    env_no_color = os.getenv("AV1_NO_COLOR")
    if env_no_color and _env_bool(env_no_color):
        no_color = True
    env_no_prompt = os.getenv("AV1_NO_PROMPT")
    if env_no_prompt and _env_bool(env_no_prompt):
        no_prompt = True

    env_log_type = os.getenv("AV1_LOG_TYPE")
    if env_log_type and (log_type == "txt"):
        log_type = env_log_type

    env_log_dir = os.getenv("AV1_LOG_DIR")
    if env_log_dir and log_dir is None:
        log_dir = env_log_dir

    # Override ffmpeg/ffprobe paths from CLI if provided
    global FFMPEG_CMD, FFPROBE_CMD
    if ffmpeg:
        FFMPEG_CMD = ffmpeg
    if ffprobe:
        FFPROBE_CMD = ffprobe
    
    # Validate parallel value
    if parallel < 1:
        cprint("⚠️  --parallel must be at least 1, setting to 1", "warning")
        parallel = 1
    elif parallel > 1:
        cprint(f"ℹ️  Note: Parallel processing (--parallel {parallel}) is currently experimental.", "info")
        cprint("    For now, files will be processed sequentially. Full parallel support coming soon!", "info")
        parallel = 1  # Force sequential for now

    # Set global no-color flag and reinitialize console
    global _NO_COLOR, _NO_PROMPT, console
    _NO_COLOR = no_color
    _NO_PROMPT = no_prompt
    if no_color:
        console = Console(no_color=True, force_terminal=True)
    
    check_ffmpeg()
    
    if not input_paths:
        # Show help when no input paths provided
        app(["--help"])
        raise typer.Exit(code=0)
    
    # If multiple paths passed (from wildcard expansion), process them all
    if len(input_paths) > 1:
        # Multiple files - treat as batch
        matched_files = [p for p in input_paths if p.lower().endswith(SUPPORTED_EXTENSIONS)]
        
        if not matched_files:
            cprint("❌ No video files found in arguments.", "error")
            raise typer.Exit(code=1)
        
        # Sort files for consistent processing order
        matched_files.sort()
        cprint(f"Found {len(matched_files)} file(s) to process.", "info")
        
        # Determine base path for relative path display (use common parent directory)
        try:
            if len(matched_files) > 1:
                base_path = os.path.commonpath(matched_files)
            else:
                base_path = os.path.dirname(matched_files[0]) or os.getcwd()
        except ValueError:
            # Files are on different drives (Windows) or no common path
            base_path = os.getcwd()
        
        # Process batch using shared helper function
        process_batch_files(
            matched_files, output_dir, base_path, bitrate, delete_original,
            overwrite, dry_run, keep_mkv, recursive=False, transient_progress=False
        )
    else:
        # Single path - could be file, directory, or wildcard pattern
        input_path = input_paths[0]
        
        # Try to expand wildcards
        if '*' in input_path or '?' in input_path:
            matched_files = glob.glob(input_path)
            if matched_files:
                matched_files = [f for f in matched_files if f.lower().endswith(SUPPORTED_EXTENSIONS)]
                if matched_files and len(matched_files) > 1:
                    # Recursively call main with expanded list
                    return main(matched_files, output_dir, bitrate, delete_original, overwrite, dry_run, recursive, keep_mkv, log_type, log_dir, version=None)
        
        # No wildcards or only 1 match - use existing logic
        convert_videos(input_path, output_dir, bitrate, delete_original, overwrite, dry_run, recursive, keep_mkv)
    
    # Save logs only if files were actually converted
    global _LOG_MESSAGES
    if _LOG_MESSAGES:
        import tempfile
        resolved_log_dir = log_dir
        if resolved_log_dir is None:
            temp_base = tempfile.gettempdir()
            resolved_log_dir = os.path.join(temp_base, "av1-logs")
        _save_log(log_type, resolved_log_dir)

if __name__ == "__main__":
    app()