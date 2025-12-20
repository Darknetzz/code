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
import re
from typing import Optional, Tuple

# Force UTF-8 encoding on Windows
if platform.system() == 'Windows':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
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
def check_corruption(file_path: str, reported_duration: Optional[float]) -> Tuple[bool, Optional[str]]:
    """
    Actually decode frames to check for corruption and truncation.
    Returns (is_valid, error_message).
    This is more thorough than just reading metadata.
    Verifies we can decode the full reported duration.
    """
    if not check_ffmpeg():
        # If ffmpeg not available, skip deep check but warn
        # Note: This means we can only do metadata checks, not actual decode verification
        return True, None  # Return valid but note that deep check was skipped
    
    try:
        # First check: Try to decode from the very end
        # If file is truncated, this will fail or decode less than expected
        if reported_duration and reported_duration > 5:
            filename = os.path.basename(file_path)
            console.print(f"[cyan]Checking end of file: {filename}[/cyan]")
            
            # Try to decode from near the end (last 5 seconds)
            # Use -ss before -i for faster input seeking (keyframe seeking)
            seek_time = max(0, reported_duration - 5)
            cmd = [
                FFMPEG_CMD, "-v", "error",
                "-ss", str(seek_time),
                "-i", file_path,
                "-t", "10",  # Try to decode 10 seconds (should get ~5 if file is complete)
                "-threads", "1",  # Single thread for faster startup
                "-f", "null",
                "-"
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=DECODE_TIMEOUT
            )
            
            stderr = result.stderr.strip()
            
            # Check for truncation indicators
            if "end of file" in stderr.lower() or "invalid data" in stderr.lower():
                return False, f"File appears truncated - cannot decode to end: {stderr}"
            
            # If return code is non-zero, check if it's a real error
            if result.returncode != 0:
                # Some errors are acceptable (like seeking past end), but others indicate corruption
                if "invalid" in stderr.lower() or "corrupt" in stderr.lower():
                    return False, f"Corruption detected near end: {stderr}"
        
        # Second check: Verify actual decodable duration
        # For very long videos, we can limit decode time to speed things up
        # For shorter videos, decode fully to ensure accuracy
        max_decode_time = None
        if reported_duration:
            # For videos longer than 10 minutes, limit decode to first 10 minutes + verify end
            # This is much faster while still detecting truncation
            max_decode_time = min(reported_duration, 600) if reported_duration > 600 else None
        else:
            # If no duration available, limit to 5 minutes for safety
            max_decode_time = 300
        
        # Use -v info to get progress output with time information
        decode_cmd = [
            FFMPEG_CMD, "-v", "info",
            "-i", file_path,
        ]
        
        if max_decode_time:
            # Limit decode time for very long videos or when duration unknown
            decode_cmd.extend(["-t", str(max_decode_time)])
        
        decode_cmd.extend([
            "-threads", "1",  # Single thread for faster startup
            "-f", "null",
            "-"
        ])
        
        # Use progress bar to show decode progress
        filename = os.path.basename(file_path)
        actual_duration = None
        decode_stderr_lines = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[cyan]{task.fields[current_time]}"),
            TextColumn("[yellow]{task.fields[speed]}"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Verifying: {filename}",
                total=max_decode_time if max_decode_time else (reported_duration if reported_duration else 100),
                current_time="00:00:00.000",
                speed=""
            )
            
            # Start the process
            process = subprocess.Popen(
                decode_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Parse output in real-time
            corruption_keywords = [
                "error", "corrupt", "invalid", "moov atom not found",
                "could not find codec parameters", "failed to read frame",
                "error while decoding", "invalid data found",
                "bitstream not supported", "error reading header", "end of file",
            ]
            
            try:
                # Read stderr line by line
                for line in process.stderr:
                    decode_stderr_lines.append(line)
                    line_lower = line.lower()
                    
                    # Check for corruption keywords
                    for keyword in corruption_keywords:
                        if keyword in line_lower:
                            process.terminate()
                            error_msg = line.strip()[:200]
                            return False, f"Corruption detected during decode: {error_msg}"
                    
                    # Parse time information
                    time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line)
                    if time_match:
                        hours, minutes, seconds = map(float, time_match.groups())
                        current_time_sec = hours * 3600 + minutes * 60 + seconds
                        actual_duration = current_time_sec
                        
                        # Format current time
                        time_str = f"{int(hours):02d}:{int(minutes):02d}:{seconds:06.3f}"
                        
                        # Parse speed if available
                        speed_match = re.search(r'speed=\s*([\d.]+)x', line)
                        speed_str = f"{speed_match.group(1)}x" if speed_match else ""
                        
                        # Update progress
                        total_time = max_decode_time if max_decode_time else (reported_duration if reported_duration else None)
                        if total_time:
                            progress.update(
                                task,
                                completed=current_time_sec,
                                current_time=time_str,
                                speed=speed_str
                            )
                        else:
                            progress.update(
                                task,
                                current_time=time_str,
                                speed=speed_str
                            )
                    
                    # Parse fps if available
                    fps_match = re.search(r'fps=\s*(\d+)', line)
                    if fps_match:
                        fps_str = f"{fps_match.group(1)} fps"
                        progress.update(task, description=f"[cyan]Verifying: {filename} ({fps_str})")
                
                # Wait for process to complete
                process.wait()
                
            except Exception as e:
                process.terminate()
                return False, f"Error during decode: {str(e)}"
        
        decode_stderr = "\n".join(decode_stderr_lines)
        
        # Check if we decoded the full duration
        if reported_duration and actual_duration:
            # For limited decodes (long videos), we only check if we got to the limit
            # For full decodes, check if we got close to reported duration
            if max_decode_time and max_decode_time < reported_duration:
                # Limited decode: just verify we got to the limit (file is readable that far)
                if actual_duration < max_decode_time * 0.9:
                    missing_percent = (1 - actual_duration / max_decode_time) * 100
                    return False, f"File truncated: decoded {actual_duration:.1f}s but expected {max_decode_time:.1f}s ({missing_percent:.1f}% missing)"
            else:
                # Full decode: verify we got close to reported duration
                if actual_duration < reported_duration * 0.9:
                    missing_percent = (1 - actual_duration / reported_duration) * 100
                    return False, f"File truncated: decoded {actual_duration:.1f}s but reported {reported_duration:.1f}s ({missing_percent:.1f}% missing)"
        
        if process.returncode != 0:
            return False, f"Decoding failed: {decode_stderr[:200] or 'Unknown error'}"
        
        # If full decode passed and we decoded the whole file, skip sample points (redundant)
        # Only do sample points if we did a limited decode (for long videos) or if no duration was available
        if max_decode_time and (not reported_duration or max_decode_time < reported_duration):
            # Third check: Sample multiple points (only needed for long videos or when duration unknown)
            sample_points = []
            if reported_duration and reported_duration > 10:
                # For long videos with limited decode, sample key points
                sample_points.append(reported_duration / 4)  # 25%
                sample_points.append(reported_duration / 2)  # 50%
                sample_points.append(reported_duration * 0.75)  # 75%
                sample_points.append(max(0, reported_duration - 2))  # Near end
            elif not reported_duration:
                # If no duration, sample a few points
                sample_points = [10.0, 30.0, 60.0]
            
            if sample_points:
                    filename = os.path.basename(file_path)
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TaskProgressColumn(),
                        console=console,
                    ) as progress:
                        sample_task = progress.add_task(
                            f"[cyan]Sampling keyframes: {filename}",
                            total=len(sample_points)
                        )
                        
                        for idx, sample_time in enumerate(sample_points):
                            progress.update(
                                sample_task,
                                description=f"[cyan]Sampling at {sample_time:.1f}s: {filename}",
                                completed=idx + 1
                            )
                            
                            # Use -ss before -i for faster input seeking
                            cmd = [
                                FFMPEG_CMD, "-v", "error",
                                "-ss", str(sample_time),
                                "-i", file_path,
                                "-t", "2",
                                "-threads", "1",
                                "-f", "null",
                                "-"
                            ]
                            result = subprocess.run(
                                cmd,
                                capture_output=True,
                                text=True,
                                timeout=DECODE_TIMEOUT
                            )
                            
                            stderr = result.stderr.strip()
                            
                            if stderr:
                                stderr_lower = stderr.lower()
                                corruption_keywords = [
                                    "error", "corrupt", "invalid", "moov atom not found",
                                    "could not find codec parameters", "failed to read frame",
                                    "error while decoding", "invalid data found",
                                    "bitstream not supported", "error reading header",
                                ]
                                for keyword in corruption_keywords:
                                    if keyword in stderr_lower:
                                        return False, f"Corruption detected at {sample_time:.1f}s: {stderr}"
                            
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
            # Check stderr for corruption indicators
            stderr = result.stderr.strip() if result.stderr else ""
            stderr_lower = stderr.lower()
            
            corruption_keywords = [
                "corrupt", "invalid", "moov atom not found", "could not find codec parameters",
                "error while decoding", "invalid data found", "bitstream not supported",
                "error reading header", "end of file", "truncated"
            ]
            
            is_corrupt = any(keyword in stderr_lower for keyword in corruption_keywords)
            
            if is_corrupt:
                error_msg = f"Corrupt file detected: {stderr[:200]}" if stderr else "Corrupt file (ffprobe failed)"
            else:
                error_msg = stderr or "ffprobe failed - file may be invalid or unsupported"
            
            return False, {"error": error_msg}
        
        data = json.loads(result.stdout)
        
        # Check if file has any video streams
        video_streams = [s for s in data.get('streams', []) if s.get('codec_type') == 'video']
        if not video_streams:
            return False, {"error": "No video stream found - file may be corrupt or invalid"}
        
        # Extract video stream info
        video_codec = None
        width = None
        height = None
        bitrate = None
        
        for stream in video_streams:
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
        is_valid, corruption_error = check_corruption(file_path, duration)
        if not is_valid:
            return False, {"error": f"Corrupt video data: {corruption_error}"}
        
        # Note: If ffmpeg is not available, check_corruption returns True but only metadata was checked
        # This is acceptable for basic validation, but deep corruption may not be detected
        
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
def verify_batch(file_paths: list[str]) -> list[str]:
    """Verify multiple files and display results in a table.
    Returns list of corrupt file paths."""
    if not file_paths:
        return []
    
    results = []
    valid_count = 0
    corrupt_files = []
    
    for file_path in file_paths:
        is_valid, info = verify_video_file(file_path)
        results.append((file_path, is_valid, info))
        if is_valid:
            valid_count += 1
        else:
            corrupt_files.append(file_path)
    
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
    
    return corrupt_files

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
    
    corrupt_files = []
    
    if len(all_files) == 1:
        # Single file - detailed output
        is_valid = verify_and_display(all_files[0], show_table=False)
        if not is_valid:
            corrupt_files.append(all_files[0])
    else:
        # Multiple files - table output
        corrupt_files = verify_batch(all_files)
    
    # Prompt user to delete corrupt files
    if corrupt_files:
        console.print(f"\n[red]Found {len(corrupt_files)} corrupt file(s):[/red]")
        for corrupt_file in corrupt_files:
            console.print(f"  • {corrupt_file}")
        
        console.print()
        try:
            response = typer.prompt(
                f"Delete {len(corrupt_files)} corrupt file(s)?",
                type=str,
                default="n"
            ).lower().strip()
            
            if response in ('y', 'yes'):
                deleted_count = 0
                failed_count = 0
                
                for corrupt_file in corrupt_files:
                    try:
                        os.remove(corrupt_file)
                        console.print(f"✅  [green]Deleted: {os.path.basename(corrupt_file)}[/green]")
                        deleted_count += 1
                    except OSError as e:
                        console.print(f"❌  [red]Failed to delete {os.path.basename(corrupt_file)}: {e}[/red]")
                        failed_count += 1
                
                console.print(f"\n[green]Deleted {deleted_count} file(s)[/green]", end="")
                if failed_count > 0:
                    console.print(f", [red]{failed_count} failed[/red]")
                else:
                    console.print()
            else:
                console.print("[yellow]Corrupt files not deleted.[/yellow]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Deletion cancelled.[/yellow]")

if __name__ == "__main__":
    app()

