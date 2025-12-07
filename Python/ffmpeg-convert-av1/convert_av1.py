# ============================================================================ #
#                                convert_av1.py                                #
# ============================================================================ #
# usage (cross-platform):
# python convert_av1.py "/path/to/videos" "/path/to/output"  (Linux/Mac)
# python convert_av1.py "C:\\Videos\\Input" "C:\\Videos\\Output"  (Windows)
# python convert_av1.py "video.mp4" --delete-original
# python convert_av1.py "/path/to/videos" -r  (recursive)

import os, subprocess, shutil, sys, json, platform, glob, time, signal, logging
from typing import Optional, Tuple
from pathlib import Path

# Force UTF-8 encoding on Windows
if platform.system() == 'Windows':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
import typer

console = Console()
app = typer.Typer()

# App metadata
__app_name__ = "convert_av1"
__version__ = "0.2.2"

# Constants
BITRATE_REDUCTION_FACTOR = 0.5
BITRATE_FALLBACK = 2_000_000
BITRATE_MAXRATE_MULTIPLIER = 1.2
BITRATE_BUFSIZE_MULTIPLIER = 2.0
SUPPORTED_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".webm")
MIN_FILE_SIZE_BYTES = 1024  # Skip files smaller than 1KB
DISK_SPACE_SAFETY_MARGIN = 1.5  # Require 1.5x file size in free space

# Global --version flag callback (used by root callback)
def _version_callback(value: bool):
    if value:
        typer.echo(f"{__app_name__} {__version__}")
        raise typer.Exit()

# Store detected encoder info (initialized with CPU fallback to satisfy static analysis)
# Structure: {"encoder": "name", "codec": "av1|hevc", "hw_type": "nvidia|amd|cpu|vaapi"}
ACTIVE_ENCODER = {"encoder": "libsvtav1", "codec": "av1", "hw_type": "cpu"}
SYSTEM_PLATFORM = platform.system().lower()  # 'windows', 'linux', 'darwin'

# Global flag to suppress cprint output during conversions
_SUPPRESS_OUTPUT = False
_PROGRESS_CONTEXT = None
_USER_CANCELLED = False
_LOG_MESSAGES = []  # Store all messages for file logging
_LOGGER = None  # Logger instance


def _format_saved(bytes_amount: float) -> str:
    """Pretty-print saved bytes as KB/MB/GB for progress columns."""
    if bytes_amount >= 1024 ** 3:
        return f"{bytes_amount / (1024 ** 3):.2f} GB"
    if bytes_amount >= 1024 ** 2:
        return f"{bytes_amount / (1024 ** 2):.1f} MB"
    if bytes_amount >= 1024:
        return f"{bytes_amount / 1024:.1f} KB"
    return "0"

def _signal_handler(sig, frame):
    """Handle Ctrl+C gracefully during batch processing."""
    global _USER_CANCELLED
    _USER_CANCELLED = True
    cprint("\n\nStopping after current file... (Press Ctrl+C again to force quit)", "warning")
    # Restore default handler so second Ctrl+C will force quit
    signal.signal(signal.SIGINT, signal.SIG_DFL)

def _save_log(log_type: str, log_path: Optional[str] = None) -> Optional[str]:
    """Save collected log messages to file (.txt or .html).
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
    
    if log_type.lower() == "html":
        log_file = os.path.join(log_dir, f"convert_av1_{timestamp}.html")
        html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>convert_av1 Log - {}</title>
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
    <h2>convert_av1 Conversion Log</h2>
    <p>Generated: {}</p>
    <div class="log">
{}
    </div>
</body>
</html>
""".format(timestamp, time.strftime("%Y-%m-%d %H:%M:%S"), "\n".join(_LOG_MESSAGES))
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(html_content)
    else:
        # Default to .txt
        log_file = os.path.join(log_dir, f"convert_av1_{timestamp}.txt")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("convert_av1 Conversion Log\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            f.write("\n".join(_LOG_MESSAGES))
    
    cprint(f"Log saved to: {log_file}", "success")
    return log_file

# ============================================================================ #
#                               FUNCTION: cprint                               #
# ============================================================================ #
def cprint(message, type="", style="bold green", **kwargs):
    if _SUPPRESS_OUTPUT:
        return
        
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
    console.print(message, style=style, **kwargs)
    
    # Log the message (with prefix for file logging)
    _LOG_MESSAGES.append(message)

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
            "ffprobe", "-v", "error", 
            "-select_streams", "v:0",
            "-show_entries", "stream=bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=1", 
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        val = result.stdout.strip()
        if val.isdigit():
            return int(val)
        
        # Fallback: Calculate from duration/size
        cmd_dur = [
            "ffprobe", "-v", "error", 
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
                # Calculate total bitrate, apply 0.9 factor to estimate video-only bitrate
                return int((size * 8 / duration) * 0.9)
            
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
            "ffmpeg", "-v", "quiet", "-f", "lavfi",
            "-i", "testsrc=size=1280x720:rate=30:duration=0.1",
            "-c:v", encoder_name, "-f", "null", "-"
        ]
        return subprocess.run(cmd, check=False, timeout=5).returncode == 0
    except Exception:
        return False

# ============================================================================ #
#                            FUNCTION: check_ffmpeg                            #
# ============================================================================ #
def check_ffmpeg():
    global ACTIVE_ENCODER
    if shutil.which("ffmpeg") is None:
        cprint("ffmpeg is not found.", "error")
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
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
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
        cprint(f"Skipping (No Transcoding Needed): {filename}", "info")
        return delete_original, 0

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
            cprint(f"Source: {input_bitrate/1_000_000:.2f}M -> Target: {target_bitrate_int/1_000_000:.2f}M", "info")
        else:
            cprint(f"Bitrate unknown. Using {BITRATE_FALLBACK/1_000_000:.1f}M fallback.", "warning")
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
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale='min(1920,iw)':-2:force_original_aspect_ratio=decrease,format={pix_fmt}",
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
    command.extend(["-c:a", "libopus", "-b:a", "64k", temp_output])

    cprint(f"Converting: {filename} using {encoder_name}", "info")

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
        cprint("Dry run: Planned conversion", "info")
        console.print(summary)
        return delete_original, 0
    
    # Get video duration for progress calculation
    try:
        duration_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                       "-of", "default=noprint_wrappers=1:nokey=1", input_path]
        duration_result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=10)
        duration_str = duration_result.stdout.strip()
        total_duration = float(duration_str) if duration_str and duration_str.replace('.', '', 1).isdigit() else None
    except:
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
            file_task = _PROGRESS_CONTEXT.add_task(
                f"[yellow]  └─ Encoding...", 
                total=100,
                saved="",
            )
            
            try:
                for line in process.stdout:
                    # Parse ffmpeg progress output
                    time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                    if time_match and total_duration:
                        hours, minutes, seconds = map(float, time_match.groups())
                        current_time = hours * 3600 + minutes * 60 + seconds
                        progress_percent = min((current_time / total_duration) * 100, 100)
                        _PROGRESS_CONTEXT.update(file_task, completed=progress_percent)
                
                process.wait()
                _PROGRESS_CONTEXT.update(file_task, completed=100)
            finally:
                if file_task is not None:
                    _PROGRESS_CONTEXT.remove_task(file_task)
                    
        elif _PROGRESS_CONTEXT and show_progress and process.stdout:
            # No duration available; show a spinner-like indeterminate bar
            file_task = _PROGRESS_CONTEXT.add_task(
                f"[yellow]  └─ Encoding...", 
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
            except:
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
                cprint(f"Done: {file_size / (1024**2):.2f} MB -> {new_file_size / (1024**2):.2f} MB (Saved: {size_saved / (1024**2):.2f} MB, {saved_percent:.1f}%)", "success")
                
                if file_size <= new_file_size:
                    cprint("Warning: File grew larger! (Entropy issue).", "warning")
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
                cprint("Error: Temp file missing or invalid!", "error")
        except OSError as e:
            cprint(f"Error swapping files: {e}", "error")
    else:
        cprint(f"Conversion failed (Code: {result.returncode})", "error")
        if os.path.exists(temp_output):
            try:
                os.remove(temp_output)
            except Exception as e:
                cprint(f"Could not remove temp file: {e}", "warning")

    return delete_original, 0

# ============================================================================ #
#                           FUNCTION: convert_videos                           #
# ============================================================================ #
def convert_videos(input_path: str, output_dir: Optional[str] = None, 
                  bitrate: Optional[str] = None, delete_original: bool = False, 
                  overwrite: bool = False, dry_run: bool = False, recursive: bool = False, keep_mkv: bool = False) -> None:
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
            cprint(f"No video files found in {mode}.", "warning")
            return
        
        # Sort files alphabetically for consistent processing order
        video_files.sort()
        
        mode_str = "recursively" if recursive else "in directory"
        cprint(f"Found {len(video_files)} video file(s) {mode_str}.", "info")
        
        # Track statistics for batch summary
        total_original_size = 0
        total_new_size = 0
        files_converted = 0
        per_file_stats = []  # Track (filename, original_size, saved_size, percent)
        cumulative_saved = 0  # Live running total saved (bytes)
        batch_start_time = time.time()  # Track elapsed time
        file_times = []  # Track individual file encoding times for ETA
        
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
            TextColumn("[green]Saved: {task.fields[saved]}"),
            transient=True,
        ) as progress:
            global _PROGRESS_CONTEXT
            _PROGRESS_CONTEXT = progress
            
            overall_task = progress.add_task(
                f"[cyan]Converting 0/{len(video_files)} files...",
                total=len(video_files),
                saved=_format_saved(0),
            )
            
            for idx, file_path in enumerate(video_files, 1):
                # Check if user cancelled
                if _USER_CANCELLED:
                    cprint("\nBatch conversion stopped by user.", "warning")
                    break
                
                # Show relative path for recursive mode
                display_path = os.path.relpath(file_path, input_path) if recursive else os.path.basename(file_path)
                file_start = time.time()
                elapsed = int(time.time() - batch_start_time)
                progress.update(overall_task, description=f"[cyan]Converting {idx}/{len(video_files)} files... ({elapsed}s) → {display_path}")
                
                # Capture original size before conversion
                try:
                    original_size = os.path.getsize(file_path)
                except:
                    original_size = 0
                
                # Determine output directory
                # Always use the same directory as the source file unless output_dir is explicitly provided
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
                auto_delete_result, size_saved = convert_single_file(file_path, current_output_dir, bitrate, delete_original, overwrite, dry_run, keep_mkv, show_progress=False)
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
                    delete_original = True
                
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
                    fields={"saved": _format_saved(cumulative_saved)},
                )
            
            _PROGRESS_CONTEXT = None
        
        # Display batch summary with space savings
        cprint(f"\nBatch conversion complete! Processed {len(video_files)} file(s).", "success")
        
        if files_converted == 0:
            cprint("No files were converted.", "info")
            return
        
        if total_original_size > 0:
            total_saved = total_original_size - total_new_size
            percent_saved = (total_saved / total_original_size) * 100
            
            # Show per-file stats if we have them
            if per_file_stats:
                cprint(f"\n📋 Per-File Summary:", style="bold cyan")
                for filename, orig_size, saved, percent in per_file_stats:
                    cprint(f"  {filename}: {saved / (1024**2):.2f} MB saved ({percent:.1f}%)", "info")
            
            cprint(f"\n📊 Total Space Savings:", style="bold cyan")
            cprint(f"  Original Size:  {total_original_size / (1024**3):.2f} GB", "info")
            cprint(f"  New Size:       {total_new_size / (1024**3):.2f} GB", "info")
            cprint(f"  Space Saved:    {total_saved / (1024**3):.2f} GB ({percent_saved:.1f}%)", "success")
    else:
        cprint("Invalid path: File or directory does not exist.", "error")

@app.command()
def main(
    input_paths: list[str] = typer.Argument(None, help="Paths to input (supports wildcards and multiple files)"),
    output_dir: Optional[str] = typer.Option(None, help="Output dir"),
    bitrate: Optional[str] = typer.Option(None, help="Override bitrate"),
    delete_original: bool = typer.Option(False, "-d", "--delete-original"),
    overwrite: bool = typer.Option(False, "-o", "--overwrite"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print planned actions without converting"),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Process subdirectories recursively"),
    keep_mkv: bool = typer.Option(False, "--keep-mkv", help="Keep .mkv extension instead of matching original filename"),
    log_type: str = typer.Option("txt", "--log-type", help="Log output type: 'txt', 'html', or 'none' to disable"),
    log_dir: Optional[str] = typer.Option(None, "--log-dir", help="Directory to save logs (default: ./logs)"),
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
    """Universal Video Compressor (AMD/NVIDIA/CPU) - Force 50% size reduction."""
    # If version flag triggered, callback already exited.
    check_ffmpeg()
    
    if not input_paths:
        cprint("Error: INPUT_PATH is required", "error")
        raise typer.Exit(code=1)
    
    # If multiple paths passed (from wildcard expansion), process them all
    if len(input_paths) > 1:
        # Multiple files - treat as batch
        matched_files = [p for p in input_paths if p.lower().endswith(SUPPORTED_EXTENSIONS)]
        
        if not matched_files:
            cprint("No video files in arguments.", "error")
            raise typer.Exit(code=1)
        
        # Sort files for consistent processing order
        matched_files.sort()
        cprint(f"Found {len(matched_files)} file(s) to process.", "info")
        
        # Set up graceful cancellation handler
        global _USER_CANCELLED
        _USER_CANCELLED = False
        signal.signal(signal.SIGINT, _signal_handler)
        
        # Process each file
        # Track statistics for batch summary
        total_original_size = 0
        total_new_size = 0
        files_converted = 0
        auto_delete = delete_original
        per_file_stats = []  # Track (filename, original_size, saved_size, percent)
        cumulative_saved = 0  # Live running total saved (bytes)
        batch_start_time = time.time()  # Track elapsed time
        file_times = []  # Track individual file encoding times for ETA
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[green]Saved: {task.fields[saved]}"),
            transient=False,
        ) as progress:
            global _PROGRESS_CONTEXT
            _PROGRESS_CONTEXT = progress
            
            overall_task = progress.add_task(
                f"[cyan]Converting 0/{len(matched_files)} files...",
                total=len(matched_files),
                saved=_format_saved(0),
            )
            
            for idx, file_path in enumerate(matched_files, 1):
                # Check if user cancelled
                if _USER_CANCELLED:
                    cprint("\nBatch conversion stopped by user.", "warning")
                    break
                
                display_name = os.path.basename(file_path)
                file_start = time.time()
                elapsed = int(time.time() - batch_start_time)
                progress.update(overall_task, description=f"[cyan]Converting {idx}/{len(matched_files)} files... ({elapsed}s) → {display_name}")
                
                # Capture original size before conversion
                try:
                    original_size = os.path.getsize(file_path)
                except:
                    original_size = 0
                
                # Suppress output during conversion
                global _SUPPRESS_OUTPUT
                _SUPPRESS_OUTPUT = True
                auto_delete_result, size_saved = convert_single_file(file_path, output_dir, bitrate, auto_delete, overwrite, dry_run, keep_mkv, show_progress=False)
                _SUPPRESS_OUTPUT = False
                
                # Track statistics if conversion happened
                if size_saved != 0:
                    files_converted += 1
                    total_original_size += original_size
                    total_new_size += (original_size - size_saved)
                    cumulative_saved += size_saved
                    saved_percent = (size_saved / original_size * 100) if original_size > 0 else 0
                    per_file_stats.append((display_name, original_size, size_saved, saved_percent))
                    
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
                    remaining_files = len(matched_files) - idx
                    eta_seconds = int(avg_time_per_file * remaining_files)
                    if eta_seconds > 0:
                        eta_str = f" | ETA: {eta_seconds}s"
                
                progress.update(
                    overall_task,
                    description=f"[cyan]Converting {idx}/{len(matched_files)} files... ({elapsed}s{eta_str}) → {display_name}",
                    fields={"saved": _format_saved(cumulative_saved)},
                )
            
            _PROGRESS_CONTEXT = None
        
        # Display batch summary
        cprint(f"\nBatch conversion complete! Processed {len(matched_files)} file(s).", "success")
        
        if files_converted == 0:
            cprint("No files were converted.", "info")
        elif total_original_size > 0:
            total_saved = total_original_size - total_new_size
            percent_saved = (total_saved / total_original_size) * 100
            
            # Show per-file stats if we have them
            if per_file_stats:
                cprint(f"\n📋 Per-File Summary:", style="bold cyan")
                for filename, orig_size, saved, percent in per_file_stats:
                    cprint(f"  {filename}: {saved / (1024**2):.2f} MB saved ({percent:.1f}%)", "info")
            
            cprint(f"\n📊 Total Space Savings:", style="bold cyan")
            cprint(f"  Original Size:  {total_original_size / (1024**3):.2f} GB", "info")
            cprint(f"  New Size:       {total_new_size / (1024**3):.2f} GB", "info")
            cprint(f"  Space Saved:    {total_saved / (1024**3):.2f} GB ({percent_saved:.1f}%)", "success")
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
    
    # Save logs
    _save_log(log_type, log_dir)

if __name__ == "__main__":
    app()