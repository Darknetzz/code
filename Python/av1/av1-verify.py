# ============================================================================ #
#                                 av1-verify.py                                #
# ============================================================================ #
# usage:
# av1-verify "video.mp4"
# av1-verify "/path/to/videos"  (checks all videos in directory)
# av1-verify "/path/to/videos" -r  (recursive)

import os
import subprocess
import shutil
import sys
import json
import platform
import glob
from typing import Optional, Tuple

# Force UTF-8 encoding on Windows
if platform.system() == 'Windows':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from rich.console import Console
from rich.table import Table
import typer

# ============================================================================ #
#                           APP & CLI CONFIGURATION                            #
# ============================================================================ #
__app_name__ = "av1-verify"
__version__ = "0.1.0"

console = Console()
app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    rich_markup_mode="rich",
)

# ============================================================================ #
#                         FILE HANDLING CONSTANTS                              #
# ============================================================================ #
SUPPORTED_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".webm")
PROBE_TIMEOUT = 10  # Timeout for ffprobe operations (seconds)

# ============================================================================ #
#                           ENVIRONMENT OVERRIDES                             #
# ============================================================================ #
FFPROBE_CMD = os.getenv("AV1_FFPROBE_PATH") or "ffprobe"
FFMPEG_CMD = os.getenv("AV1_FFMPEG_PATH") or "ffmpeg"
DECODE_TIMEOUT = 30  # Timeout for corruption check (seconds)

# ============================================================================ #
#                         FUNCTION: check_ffprobe                             #
# ============================================================================ #
def check_ffprobe() -> None:
    """Check if ffprobe is available."""
    global FFPROBE_CMD
    ffprobe_ok = shutil.which(FFPROBE_CMD) or (os.path.exists(FFPROBE_CMD) and os.path.isfile(FFPROBE_CMD))
    if not ffprobe_ok:
        path_ffprobe = shutil.which("ffprobe")
        if path_ffprobe:
            FFPROBE_CMD = path_ffprobe
        else:
            console.print("❌  ffprobe is not found.", style="red")
            raise typer.Exit(code=1)

# ============================================================================ #
#                         FUNCTION: check_ffmpeg                               #
# ============================================================================ #
def check_ffmpeg() -> bool:
    """Check if ffmpeg is available. Returns True if available."""
    global FFMPEG_CMD
    ffmpeg_ok = shutil.which(FFMPEG_CMD) or (os.path.exists(FFMPEG_CMD) and os.path.isfile(FFMPEG_CMD))
    if not ffmpeg_ok:
        path_ffmpeg = shutil.which("ffmpeg")
        if path_ffmpeg:
            FFMPEG_CMD = path_ffmpeg
            return True
        return False
    return True

# ============================================================================ #
#                      FUNCTION: check_corruption                             #
# ============================================================================ #
def check_corruption(file_path: str) -> Tuple[bool, Optional[str]]:
    """
    Actually decode frames to check for corruption.
    Returns (is_valid, error_message).
    This is more thorough than just reading metadata.
    Samples multiple points in the video to catch corruption.
    """
    if not check_ffmpeg():
        # If ffmpeg not available, skip deep check
        return True, None
    
    try:
        # First, get the duration to sample different points
        duration_cmd = [
            FFPROBE_CMD, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        duration_result = subprocess.run(
            duration_cmd,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT
        )
        
        duration = None
        if duration_result.returncode == 0:
            try:
                duration = float(duration_result.stdout.strip())
            except (ValueError, TypeError):
                pass
        
        # Sample points: start, middle, end (if duration available)
        # Otherwise just check the beginning
        sample_points = [0.0]  # Always check start
        if duration and duration > 10:
            sample_points.append(duration / 2)  # Middle
            sample_points.append(max(0, duration - 5))  # Near end
        
        # Check each sample point
        for sample_time in sample_points:
            # Use ffmpeg to attempt to decode a few frames from this point
            # -ss: seek to position
            # -t 2: decode 2 seconds worth of frames
            # -v error: only show errors
            # -f null: output to null (we don't need the decoded video)
            cmd = [
                FFMPEG_CMD, "-v", "error",
                "-ss", str(sample_time),
                "-i", file_path,
                "-t", "2",  # Check 2 seconds worth of frames
                "-f", "null",
                "-"
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=DECODE_TIMEOUT
            )
            
            # Check stderr for error messages
            stderr = result.stderr.strip()
            
            # Common corruption indicators
            corruption_keywords = [
                "error",
                "corrupt",
                "invalid",
                "moov atom not found",
                "could not find codec parameters",
                "failed to read frame",
                "error while decoding",
                "invalid data found",
                "bitstream not supported",
                "error reading header",
            ]
            
            # If there are errors in stderr, check if they indicate corruption
            if stderr:
                stderr_lower = stderr.lower()
                for keyword in corruption_keywords:
                    if keyword in stderr_lower:
                        return False, f"Corruption detected at {sample_time:.1f}s: {stderr}"
            
            # If return code is non-zero, there was an error
            if result.returncode != 0:
                return False, f"Decoding failed at {sample_time:.1f}s: {stderr or 'Unknown error'}"
        
        return True, None
        
    except subprocess.TimeoutExpired:
        return False, "Timeout during corruption check"
    except Exception as e:
        return False, f"Error during corruption check: {str(e)}"

# ============================================================================ #
#                      FUNCTION: format_duration                              #
# ============================================================================ #
def format_duration(seconds: float) -> str:
    """Format duration in seconds to HH:MM:SS.mmm format."""
    if seconds is None:
        return "N/A"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{int(minutes):02d}:{secs:06.3f}"

# ============================================================================ #
#                      FUNCTION: format_size                                  #
# ============================================================================ #
def format_size(bytes_amount: int) -> str:
    """Format file size in bytes to human-readable format."""
    if bytes_amount >= 1024 ** 3:
        return f"{bytes_amount / (1024 ** 3):.2f} GB"
    if bytes_amount >= 1024 ** 2:
        return f"{bytes_amount / (1024 ** 2):.2f} MB"
    if bytes_amount >= 1024:
        return f"{bytes_amount / 1024:.2f} KB"
    return f"{bytes_amount} B"

# ============================================================================ #
#                      FUNCTION: verify_video_file                            #
# ============================================================================ #
def verify_video_file(file_path: str) -> Tuple[bool, Optional[dict]]:
    """
    Verify a video file and extract information.
    Returns (is_valid, info_dict) where info_dict contains:
    - codec: video codec name
    - duration: duration in seconds
    - size: file size in bytes
    - width: video width
    - height: video height
    - bitrate: bitrate if available
    """
    if not os.path.isfile(file_path):
        return False, None
    
    # Get file size
    try:
        file_size = os.path.getsize(file_path)
    except OSError:
        return False, None
    
    # Use ffprobe to check if file is valid and get metadata
    try:
        cmd = [
            FFPROBE_CMD, "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=PROBE_TIMEOUT)
        
        if result.returncode != 0:
            # File is likely corrupt or invalid
            return False, {"error": result.stderr.strip() or "ffprobe failed"}
        
        data = json.loads(result.stdout)
        
        # Extract video stream info
        video_codec = None
        width = None
        height = None
        bitrate = None
        
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_codec = stream.get('codec_name', 'unknown')
                width = stream.get('width')
                height = stream.get('height')
                bitrate = stream.get('bit_rate')
                if bitrate:
                    try:
                        bitrate = int(bitrate)
                    except (ValueError, TypeError):
                        bitrate = None
                break
        
        # Extract duration
        format_info = data.get('format', {})
        duration_str = format_info.get('duration')
        duration = None
        if duration_str:
            try:
                duration = float(duration_str)
            except (ValueError, TypeError):
                pass
        
        # If we have format bitrate but not stream bitrate, use format bitrate
        if not bitrate:
            format_bitrate = format_info.get('bit_rate')
            if format_bitrate:
                try:
                    bitrate = int(format_bitrate)
                except (ValueError, TypeError):
                    pass
        
        # Now perform actual corruption check by attempting to decode frames
        is_valid, corruption_error = check_corruption(file_path)
        if not is_valid:
            return False, {"error": f"Corrupt video data: {corruption_error}"}
        
        return True, {
            "codec": video_codec or "unknown",
            "duration": duration,
            "size": file_size,
            "width": width,
            "height": height,
            "bitrate": bitrate,
        }
        
    except subprocess.TimeoutExpired:
        return False, {"error": "Timeout while probing file"}
    except json.JSONDecodeError:
        return False, {"error": "Invalid JSON response from ffprobe"}
    except Exception as e:
        return False, {"error": str(e)}

# ============================================================================ #
#                      FUNCTION: verify_and_display                           #
# ============================================================================ #
def verify_and_display(file_path: str, show_table: bool = False) -> bool:
    """
    Verify a single file and display results.
    Returns True if file is valid, False otherwise.
    """
    is_valid, info = verify_video_file(file_path)
    
    if not is_valid:
        error_msg = info.get("error", "Unknown error") if info else "File not found"
        console.print(f"❌  [red]{os.path.basename(file_path)}[/red] - Corrupt or invalid: {error_msg}")
        return False
    
    if show_table:
        # Will be handled by batch display
        return True
    
    # Single file display
    console.print(f"\n✅  [green]{os.path.basename(file_path)}[/green]")
    console.print(f"   Codec:  [cyan]{info['codec']}[/cyan]")
    console.print(f"   Length: [cyan]{format_duration(info['duration'])}[/cyan]")
    console.print(f"   Size:   [cyan]{format_size(info['size'])}[/cyan] ({info['size']:,} bytes)")
    
    if info.get('width') and info.get('height'):
        console.print(f"   Resolution: [cyan]{info['width']}x{info['height']}[/cyan]")
    
    if info.get('bitrate'):
        bitrate_mbps = info['bitrate'] / 1_000_000
        console.print(f"   Bitrate: [cyan]{bitrate_mbps:.2f} Mbps[/cyan]")
    
    return True

# ============================================================================ #
#                      FUNCTION: verify_batch                                 #
# ============================================================================ #
def verify_batch(file_paths: list[str]) -> None:
    """Verify multiple files and display results in a table."""
    if not file_paths:
        return
    
    results = []
    valid_count = 0
    
    for file_path in file_paths:
        is_valid, info = verify_video_file(file_path)
        results.append((file_path, is_valid, info))
        if is_valid:
            valid_count += 1
    
    # Create table
    table = Table(title=f"Video Verification Results ({valid_count}/{len(results)} valid)")
    table.add_column("File", style="cyan", no_wrap=False)
    table.add_column("Status", style="bold")
    table.add_column("Codec", style="yellow")
    table.add_column("Length", style="green")
    table.add_column("Size", style="blue")
    
    for file_path, is_valid, info in results:
        filename = os.path.basename(file_path)
        
        if not is_valid:
            error = info.get("error", "Unknown error") if info else "Not found"
            table.add_row(
                filename,
                "[red]❌ Corrupt[/red]",
                "-",
                "-",
                "-"
            )
        else:
            table.add_row(
                filename,
                "[green]✅ Valid[/green]",
                info.get('codec', 'unknown'),
                format_duration(info.get('duration')),
                format_size(info.get('size', 0))
            )
    
    console.print()
    console.print(table)
    console.print()

@app.command()
def main(
    input_paths: list[str] = typer.Argument(None, help="File or directory path(s) to verify"),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Process subdirectories recursively"),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=lambda v: (typer.echo(f"{__app_name__} {__version__}"), typer.Exit()) if v else None,
        is_eager=True,
        is_flag=True,
    ),
):
    """
    Verify video files and display codec, length, and size information.
    
    Checks if video files are not corrupt and outputs their codec, duration, and file size.
    """
    check_ffprobe()
    
    if not input_paths:
        app(["--help"])
        raise typer.Exit(code=0)
    
    all_files = []
    
    for input_path in input_paths:
        if os.path.isfile(input_path):
            if input_path.lower().endswith(SUPPORTED_EXTENSIONS):
                all_files.append(input_path)
        elif os.path.isdir(input_path):
            if recursive:
                for root, dirs, files in os.walk(input_path):
                    for filename in files:
                        if filename.lower().endswith(SUPPORTED_EXTENSIONS):
                            all_files.append(os.path.join(root, filename))
            else:
                for filename in os.listdir(input_path):
                    file_path = os.path.join(input_path, filename)
                    if os.path.isfile(file_path) and filename.lower().endswith(SUPPORTED_EXTENSIONS):
                        all_files.append(file_path)
        else:
            # Try wildcard expansion
            if '*' in input_path or '?' in input_path:
                matched = glob.glob(input_path)
                for match in matched:
                    if os.path.isfile(match) and match.lower().endswith(SUPPORTED_EXTENSIONS):
                        all_files.append(match)
            else:
                console.print(f"❌  [red]Path not found: {input_path}[/red]")
    
    if not all_files:
        console.print("❌  [red]No video files found.[/red]")
        raise typer.Exit(code=1)
    
    # Remove duplicates and sort
    all_files = sorted(list(set(all_files)))
    
    if len(all_files) == 1:
        # Single file - detailed output
        verify_and_display(all_files[0], show_table=False)
    else:
        # Multiple files - table output
        verify_batch(all_files)

if __name__ == "__main__":
    app()

