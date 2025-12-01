r"""
# ============================================================================ #
#                                convert_av1.py                                #
# ============================================================================ #
# usage:
# python convert_av1.py "C:\Videos\Input" "C:\Videos\Output" --bitrate 8M
# python convert_av1.py "C:\Videos\Input" --bitrate 8M
# python convert_av1.py "C:\Videos\video.mp4" --bitrate 8M
# python convert_av1.py "C:\Videos\video.mp4" --bitrate 8M --delete-original
"""

import os, subprocess, shutil, sys, json
from typing import Optional
from rich.console import Console
import typer

console = Console()
app = typer.Typer()

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
#                            FUNCTION: check_ffmpeg                            #
# ============================================================================ #
def check_ffmpeg():
    if shutil.which("ffmpeg") is None:
        cprint("ffmpeg is not found in your system PATH.", "error")
        raise typer.Exit(code=1)

# ============================================================================ #
#                          FUNCTION: needs_transcoding                         #
# ============================================================================ #
def needs_transcoding(file_path):
    """
    Returns True if the file needs transcoding (i.e., video is NOT av1).
    Returns False if video is already av1 or if no video stream exists.
    """
    try:
        # We ask for all streams, formatted as JSON, quietly (-v quiet)
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        # Iterate through streams to find the Video stream
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                codec = stream.get('codec_name')
                
                # The core check: Is it already AV1?
                if codec == 'av1':
                    print(f"Skipping {file_path}: Already AV1.")
                    return False
                
                # Optional: You can add logic here to re-encode AV1 
                # if it's the WRONG kind of AV1 (e.g., massive bitrate)
                # but for now, we assume if it's AV1, it's good.
                return True

        # If we get here, it's probably an audio file or has no video
        print(f"Skipping {file_path}: No video stream found.")
        return False
    except Exception as e:
        print(f"Error probing {file_path}: {e}")
        return False
        # Safety: Don't encode if we can't read it

# ============================================================================ #
#                        FUNCTION: maybe_delete_original                       #
# ============================================================================ #
def maybe_delete_original(original_path, auto_delete=False):
    try:
        if auto_delete:
            os.remove(original_path)
            cprint(f"Deleted original: {original_path}")
            return True
        resp = input(f"Delete original file?\n{original_path}\n[y/N/a]: ").strip().lower()
        if resp in ("y", "yes"):
            os.remove(original_path)
            cprint("Original deleted.", "success")
            return False
        elif resp in ("a", "all"):
            os.remove(original_path)
            cprint("Original deleted.", "success")
            cprint("Auto-delete enabled for remaining files.", "info")
            return True  # Signal to enable auto-delete for remaining files
        else:
            cprint("Kept original.", "info")
            return False
    except Exception as e:
        cprint(f"Could not delete {original_path}: {e}", "warning")
    return False

# ============================================================================ #
#                         FUNCTION: convert_single_file                        #
# ============================================================================ #
def convert_single_file(input_path, output_dir=None, bitrate=None, delete_original=False, overwrite=False):
    filename = os.path.basename(input_path)
    
    if not input_path.lower().endswith(".mp4") and not input_path.lower().endswith(".mkv"):
        cprint(f"File '{input_path}' is not an MP4 or MKV file, skipping...", "info")
        return

    # Check if transcoding is needed
    if not needs_transcoding(input_path):
        cprint(f"Skipping conversion for {filename} because it is already of AV1 format.", "info")
        return

    # Determine Output Paths
    if output_dir is None:
        output_dir = os.path.dirname(input_path)
        output_name = os.path.splitext(filename)[0] + "-AV1.mkv"
    else:
        os.makedirs(output_dir, exist_ok=True)
        output_name = os.path.splitext(filename)[0] + "_av1.mkv"
    
    output_path = os.path.join(output_dir, output_name)
    temp_output = f"{output_path}.temp.mkv"  # <--- Atomic Swap Temp File

    # Check if final output already exists (Safety Check)
    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        if overwrite:
            cprint(f"Overwriting existing file: {output_path}", "warning")
            # We don't delete here; atomic swap will replace it at the end.
        else:
            resp = input(f"Output file already exists: {output_path}\nDo you want to delete it and proceed? [y/N]: ").strip().lower()
            if not resp in ("y", "yes"):
                cprint(f"Skipping conversion for {filename}.", "info")
                return

    # Check file size before conversion
    file_size = os.path.getsize(input_path)
    if file_size == 0:
        cprint(f"Skipping zero-byte file: {filename}", "warning")
        return

    # Base command arguments (Hardware Agnostic / Apple Compatible)
    command = [
        "ffmpeg",
        "-y", # Overwrite the TEMP file if it exists (leftover from crash)
        "-i", input_path,
        
        # --- VIDEO FILTERS ---
        # Scale to max 1080p, prevent upscaling (force_original...=decrease), 
        # and ensure pixel format is compatible (yuv420p is the safest for players)
        "-vf", "scale='min(1920,iw)':-2:force_original_aspect_ratio=decrease,format=yuv420p",
        
        # --- VIDEO ENCODER (CPU) ---
        "-c:v", "libsvtav1",
        "-preset", "6",       # 6 is the sweet spot. 4 is slow/best, 8 is fast.
        "-g", "240",          # Keyframe interval (10s at 24fps). Good for seeking.
        
        # --- COMPATIBILITY FLAGS ---
        "-movflags", "+faststart",
        "-metadata", "major_brand=mp42",
        "-metadata", "compatible_brands=mp42av01iso2mp41",
        
        # --- AUDIO ENCODER ---
        "-c:a", "libopus",
        "-b:a", "128k",       # 128k Opus ~= 256k MP3. Plenty for stereo.
        "-ac", "2",           # Force Stereo
    ]

    # --- Rate Control Logic ---
    target_bitrate_int = 0
    
    if bitrate:
        # User explicitly requested a bitrate -> Use VBR Mode
        cprint(f"Using user-specified bitrate: {bitrate}", "info")
        if isinstance(bitrate, str):
            try:
                if bitrate.lower().endswith('k'):
                    target_bitrate_int = int(bitrate[:-1]) * 1000
                elif bitrate.lower().endswith('m'):
                    target_bitrate_int = int(bitrate[:-1]) * 1000000
                else:
                    target_bitrate_int = int(bitrate)
            except ValueError:
                cprint(f"Invalid bitrate format: {bitrate}. Falling back to CRF.", "error")
                target_bitrate_int = 0
        else:
            target_bitrate_int = bitrate

    if target_bitrate_int > 0:
        # VBR Mode (Constrained Bitrate)
        max_rate = int(target_bitrate_int * 1.5)
        buf_size = int(target_bitrate_int * 2)
        command.extend([
            "-b:v", str(target_bitrate_int),
            "-maxrate", str(max_rate),
            "-bufsize", str(buf_size)
        ])
    else:
        # CRF Mode (Quality Based) - Default
        # Replaces old "60% of original" logic which is unreliable
        cprint("No bitrate specified. Using CRF 26 (High Quality / Balanced).", "info")
        command.extend(["-crf", "26"])

    # Write to TEMP path first
    command.append(temp_output)

    cprint(f"Command: {' '.join(command)}", "info")
    cprint(f"Converting: {filename}", "info")
    
    # Run FFmpeg (check=False so we can handle errors manually)
    result = subprocess.run(command, check=False)

    if result.returncode == 0:
        # SUCCESS: Perform Atomic Swap
        try:
            if os.path.exists(temp_output):
                os.replace(temp_output, output_path)
                
                new_file_size = os.path.getsize(output_path)
                cprint(f"Converted {filename}: {file_size / (1024**2):.2f} MB -> {new_file_size / (1024**2):.2f} MB", "success")
                
                if file_size <= new_file_size:
                    cprint(f"Converted file is not smaller than original for {filename}. Keeping original.", "warning")
                else:
                    enable_auto = maybe_delete_original(input_path, auto_delete=delete_original)
                    if enable_auto:
                        delete_original = True
            else:
                cprint(f"Error: FFmpeg reported success, but temp file {temp_output} is missing!", "error")
        except OSError as e:
            cprint(f"Error swapping temp file to final path: {e}", "error")
    else:
        # FAILURE: Clean up temp file
        cprint(f"Conversion failed for {filename} (Error code: {result.returncode})", "error")
        if os.path.exists(temp_output):
            os.remove(temp_output)

    return delete_original

# ============================================================================ #
#                           FUNCTION: convert_videos                           #
# ============================================================================ #
def convert_videos(input_path, output_dir=None, bitrate=None, delete_original=False, overwrite=False):
    # Auto-detect if input is a file or directory
    if os.path.isfile(input_path):
        convert_single_file(input_path, output_dir, bitrate, delete_original, overwrite)
    elif os.path.isdir(input_path):
        if output_dir is None:
            output_dir = input_path
        else:
            os.makedirs(output_dir, exist_ok=True)

        for filename in os.listdir(input_path):
            if filename.lower().endswith(".mp4") or filename.lower().endswith(".mkv"):
                file_path = os.path.join(input_path, filename)
                # Pass delete_original by reference through function calls logic
                result_delete_flag = convert_single_file(file_path, output_dir, bitrate, delete_original, overwrite)
                
                # If user selected "All" in the prompt, update the flag for future loops
                if isinstance(result_delete_flag, bool) and result_delete_flag:
                    delete_original = True
    else:
        cprint(f"{input_path} is neither a valid file nor directory.", "error")
        raise typer.Exit(code=1)

    cprint("All conversions complete.", "success")

# ============================================================================ #
#                                FUNCTION: main                                #
# ============================================================================ #
@app.command()
def main(
    input_path: str = typer.Argument(..., help="Path to input file or directory containing .mp4 files"),
    output_dir: Optional[str] = typer.Argument(None, help="Path to output directory for converted files (optional)"),
    bitrate: Optional[str] = typer.Option(None, help="Target video bitrate (default: CRF 26)"),
    delete_original: bool = typer.Option(False, "-d", "--delete-original", 
                                         help="Delete original files after successful conversion without prompting"),
    overwrite: bool = typer.Option(False, "-o", "--overwrite", 
                                   help="Force overwrite destination file")
):
    """Batch convert MP4s to AV1 using libsvtav1 (CPU)."""
    check_ffmpeg()
    convert_videos(input_path, output_dir, bitrate, delete_original, overwrite)

if __name__ == "__main__":
    app()