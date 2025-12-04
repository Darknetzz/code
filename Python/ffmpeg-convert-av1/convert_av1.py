# ============================================================================ #
#                                convert_av1.py                                #
# ============================================================================ #
# usage:
# python convert_av1.py "C:\Videos\Input" "C:\Videos\Output"
# python convert_av1.py "C:\Videos\video.mp4" --delete-original

import os, subprocess, shutil, sys, json
from typing import Optional, Tuple
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import typer

console = Console()
app = typer.Typer()

# App metadata
__app_name__ = "convert_av1"
__version__ = "0.2.1"

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
# Structure: {"encoder": "name", "codec": "av1|hevc", "hw_type": "nvidia|amd|cpu"}
ACTIVE_ENCODER = {"encoder": "libsvtav1", "codec": "av1", "hw_type": "cpu"}

# ============================================================================ #
#                               FUNCTION: cprint                               #
# ============================================================================ #
def cprint(message, type="", style="bold green", **kwargs):
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
    
    # --- PRIORITY 1: AV1 HARDWARE (RTX 40-series / RX 7000-series) ---
    if check_encoder_support("av1_nvenc"):
        ACTIVE_ENCODER = {"encoder": "av1_nvenc", "codec": "av1", "hw_type": "nvidia"}
        cprint("Hardware Found: NVIDIA AV1 (`av1_nvenc`).", "success")
        return
        
    if check_encoder_support("av1_amf"):
        ACTIVE_ENCODER = {"encoder": "av1_amf", "codec": "av1", "hw_type": "amd"}
        cprint("Hardware Found: AMD AV1 (`av1_amf`).", "success")
        return

    # --- PRIORITY 2: HEVC HARDWARE (GTX 900+ / RX 5000+) ---
    if check_encoder_support("hevc_nvenc"):
        ACTIVE_ENCODER = {"encoder": "hevc_nvenc", "codec": "hevc", "hw_type": "nvidia"}
        cprint("Hardware Found: NVIDIA HEVC (`hevc_nvenc`).", "success")
        return

    if check_encoder_support("hevc_amf"):
        ACTIVE_ENCODER = {"encoder": "hevc_amf", "codec": "hevc", "hw_type": "amd"}
        cprint("Hardware Found: AMD HEVC (`hevc_amf`).", "success")
        return

    # --- PRIORITY 3: CPU FALLBACK ---
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
            
        resp = input(f"Delete original file?\n{original_path}\n[y/N/a]: ").strip().lower()
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
                       overwrite: bool = False, dry_run: bool = False) -> Tuple[bool, int]:
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
            if input(f"File exists: {output_path}. Delete? [y/N]: ").lower() not in ("y", "yes"):
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
    # Hardware Encoders (NVENC/AMF) prefer 'nv12'. CPU prefers 'yuv420p'.
    pix_fmt = "yuv420p" if ACTIVE_ENCODER["hw_type"] == "cpu" else "nv12"
    
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
    
    try:
        result = subprocess.run(command, check=False)
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
                cprint(f"Done: {file_size / (1024**2):.2f} MB -> {new_file_size / (1024**2):.2f} MB", "success")
                
                if file_size <= new_file_size:
                    cprint("Warning: File grew larger! (Entropy issue).", "warning")
                    # Still offer to delete if user wants
                    auto_delete_flag = maybe_delete_original(input_path, auto_delete=delete_original)
                    # Track if original was deleted in this step
                    original_deleted = not os.path.exists(input_path)
                    if auto_delete_flag:
                        delete_original = True
                    # If original was deleted, rename output to original name when same directory
                    if original_deleted and os.path.dirname(output_path) == os.path.dirname(input_path):
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
                    
                    # Rename converted file to original name if original was deleted
                    if original_deleted and os.path.dirname(output_path) == os.path.dirname(input_path):
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
                  overwrite: bool = False, dry_run: bool = False, recursive: bool = False) -> None:
    """
    Main entry point for converting videos.
    Handles both single files and directory processing.
    Supports recursive subdirectory traversal when recursive=True.
    """
    if os.path.isfile(input_path):
        # Single file - no batch summary needed
        convert_single_file(input_path, output_dir, bitrate, delete_original, overwrite, dry_run)
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
        
        mode_str = "recursively" if recursive else "in directory"
        cprint(f"Found {len(video_files)} video file(s) {mode_str}.", "info")
        
        # Track statistics for batch summary
        total_original_size = 0
        total_new_size = 0
        files_converted = 0
        
        # Process files with progress tracking
        for idx, file_path in enumerate(video_files, 1):
            # Show relative path for recursive mode
            display_path = os.path.relpath(file_path, input_path) if recursive else os.path.basename(file_path)
            cprint(f"\n[{idx}/{len(video_files)}] Processing: {display_path}", style="bold cyan")
            
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
            
            auto_delete_result, size_saved = convert_single_file(file_path, current_output_dir, bitrate, delete_original, overwrite, dry_run)
            
            # Track statistics if conversion happened
            if size_saved != 0:
                files_converted += 1
                total_original_size += original_size
                total_new_size += (original_size - size_saved)
            
            # Update auto-delete flag based on user's "all" choice
            if auto_delete_result:
                delete_original = True
        
        # Display batch summary with space savings
        cprint(f"\nBatch conversion complete! Processed {len(video_files)} file(s).", "success")
        
        if files_converted > 0 and total_original_size > 0:
            total_saved = total_original_size - total_new_size
            percent_saved = (total_saved / total_original_size) * 100
            
            cprint(f"\n📊 Space Savings Summary:", style="bold cyan")
            cprint(f"  Original Size:  {total_original_size / (1024**3):.2f} GB", "info")
            cprint(f"  New Size:       {total_new_size / (1024**3):.2f} GB", "info")
            cprint(f"  Space Saved:    {total_saved / (1024**3):.2f} GB ({percent_saved:.1f}%)", "success")
    else:
        cprint("Invalid path: File or directory does not exist.", "error")

@app.callback(invoke_without_command=True)
def main(
    input_path: str = typer.Argument(..., help="Path to input"),
    output_dir: Optional[str] = typer.Argument(None, help="Output dir"),
    bitrate: Optional[str] = typer.Option(None, help="Override bitrate"),
    delete_original: bool = typer.Option(False, "-d", "--delete-original"),
    overwrite: bool = typer.Option(False, "-o", "--overwrite"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print planned actions without converting"),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Process subdirectories recursively"),
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
    convert_videos(input_path, output_dir, bitrate, delete_original, overwrite, dry_run, recursive)

if __name__ == "__main__":
    app()