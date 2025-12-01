# ============================================================================ #
#                                convert_av1.py                                #
# ============================================================================ #
# usage:
# python convert_av1.py "C:\Videos\Input" "C:\Videos\Output" --bitrate 8M
# python convert_av1.py "C:\Videos\video.mp4" --delete-original

import os, subprocess, shutil, sys, json
from typing import Optional
from rich.console import Console
import typer

console = Console()
app = typer.Typer()

# Global flag to cache detection result so we don't check every single file
HAS_AMD_GPU = False

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
#                       FUNCTION: check_hardware_encoder                       #
# ============================================================================ #
def check_hardware_encoder(encoder_name="av1_amf"):
    """
    Checks if a specific FFmpeg encoder is available and working.
    Returns True if the encoder is usable.
    """
    try:
        # We try to encode 1 frame of black video to null. 
        # If this succeeds, the hardware is present and drivers are working.
        cmd = [
            "ffmpeg",
            "-v", "quiet",
            "-f", "lavfi",
            "-i", "color=c=black:s=64x64:d=0.01",
            "-c:v", encoder_name,
            "-f", "null",
            "-"
        ]
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except Exception:
        return False

# ============================================================================ #
#                            FUNCTION: check_ffmpeg                            #
# ============================================================================ #
def check_ffmpeg():
    if shutil.which("ffmpeg") is None:
        cprint("ffmpeg is not found in your system PATH.", "error")
        raise typer.Exit(code=1)
    
    # Check for AMD GPU availability once at startup
    global HAS_AMD_GPU
    cprint("Checking for AMD GPU (av1_amf)...", "info")
    if check_hardware_encoder("av1_amf"):
        HAS_AMD_GPU = True
        cprint("AMD GPU Detected! Using 'av1_amf' for hardware acceleration.", "success")
    else:
        HAS_AMD_GPU = False
        cprint("No AMD GPU detected (or av1_amf unavailable). Falling back to CPU 'libsvtav1'.", "warning")

# ============================================================================ #
#                          FUNCTION: needs_transcoding                         #
# ============================================================================ #
def needs_transcoding(file_path):
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            file_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                codec = stream.get('codec_name')
                if codec == 'av1':
                    print(f"Skipping {file_path}: Already AV1.")
                    return False
                return True

        print(f"Skipping {file_path}: No video stream found.")
        return False
    except Exception as e:
        print(f"Error probing {file_path}: {e}")
        return False

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
            return True
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
    
    if not input_path.lower().endswith((".mp4", ".mkv")):
        cprint(f"File '{input_path}' is not an MP4 or MKV file, skipping...", "info")
        return

    if not needs_transcoding(input_path):
        cprint(f"Skipping conversion for {filename} because it is already of AV1 format.", "info")
        return

    if output_dir is None:
        output_dir = os.path.dirname(input_path)
        output_name = os.path.splitext(filename)[0] + "-AV1.mkv"
    else:
        os.makedirs(output_dir, exist_ok=True)
        output_name = os.path.splitext(filename)[0] + "_av1.mkv"
    
    output_path = os.path.join(output_dir, output_name)
    temp_output = f"{output_path}.temp.mkv"

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        if overwrite:
            cprint(f"Overwriting existing file: {output_path}", "warning")
        else:
            resp = input(f"Output file already exists: {output_path}\nDo you want to delete it and proceed? [y/N]: ").strip().lower()
            if not resp in ("y", "yes"):
                cprint(f"Skipping conversion for {filename}.", "info")
                return

    file_size = os.path.getsize(input_path)
    if file_size == 0:
        cprint(f"Skipping zero-byte file: {filename}", "warning")
        return

    # ------------------------------------------------------------------------ #
    #                       BUILDING THE COMMAND DYNAMICALLY                   #
    # ------------------------------------------------------------------------ #
    
    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", "scale='min(1920,iw)':-2:force_original_aspect_ratio=decrease,format=yuv420p",
        # Apple / Web Compatibility Flags
        "-movflags", "+faststart",
        "-metadata", "major_brand=mp42",
        "-metadata", "compatible_brands=mp42av01iso2mp41",
    ]

    # --- Video Encoder Selection (The Fork) ---
    if HAS_AMD_GPU:
        # GPU PATH (Fast & Small)
        command.extend([
            "-c:v", "av1_amf",
            "-usage", "transcoding",
            "-quality", "balanced",
            "-profile:v", "main",
        ])
    else:
        # CPU PATH (Compatible & Small)
        command.extend([
            "-c:v", "libsvtav1",
            "-preset", "8", # Faster preset for mass archiving
            "-g", "240",
        ])

    # --- Rate Control Logic (Bitrate vs Quality) ---
    target_bitrate_int = 0
    if bitrate:
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
                cprint(f"Invalid bitrate format. Falling back to default quality.", "error")
                target_bitrate_int = 0
        else:
            target_bitrate_int = bitrate

    if target_bitrate_int > 0:
        # VBR Mode (Target Bitrate)
        max_rate = int(target_bitrate_int * 1.5)
        buf_size = int(target_bitrate_int * 2)
        command.extend([
            "-b:v", str(target_bitrate_int),
            "-maxrate", str(max_rate),
            "-bufsize", str(buf_size)
        ])
    else:
        # MAX COMPRESSION MODE (CRF/QP 45)
        # We pushed these values way up to prioritize small file size over quality.
        if HAS_AMD_GPU:
            cprint("GPU Mode: Using CQP 45 (Aggressive Compression)", "info")
            command.extend([
                "-rc", "cqp", 
                "-qp_i", "45", 
                "-qp_p", "45",
            ])
        else:
            cprint("CPU Mode: Using CRF 45 (Aggressive Compression)", "info")
            command.extend(["-crf", "45"])

    # --- Audio Encoder (Reduced to 64k for size) ---
    command.extend([
        "-c:a", "libopus",
        "-b:a", "64k", # 64k is "good enough" and saves space
        "-ac", "2",
        temp_output 
    ])

    cprint(f"Command: {' '.join(command)}", "info")
    cprint(f"Converting: {filename}", "info")
    
    result = subprocess.run(command, check=False)

    if result.returncode == 0:
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
                cprint(f"Error: FFmpeg success, but temp file missing!", "error")
        except OSError as e:
            cprint(f"Error swapping files: {e}", "error")
    else:
        cprint(f"Conversion failed for {filename} (Error: {result.returncode})", "error")
        if os.path.exists(temp_output):
            os.remove(temp_output)

    return delete_original

# ============================================================================ #
#                           FUNCTION: convert_videos                           #
# ============================================================================ #
def convert_videos(input_path, output_dir=None, bitrate=None, delete_original=False, overwrite=False):
    if os.path.isfile(input_path):
        convert_single_file(input_path, output_dir, bitrate, delete_original, overwrite)
    elif os.path.isdir(input_path):
        if output_dir is None:
            output_dir = input_path
        else:
            os.makedirs(output_dir, exist_ok=True)

        for filename in os.listdir(input_path):
            if filename.lower().endswith((".mp4", ".mkv")):
                file_path = os.path.join(input_path, filename)
                result_delete_flag = convert_single_file(file_path, output_dir, bitrate, delete_original, overwrite)
                
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
    input_path: str = typer.Argument(..., help="Path to input file or directory"),
    output_dir: Optional[str] = typer.Argument(None, help="Path to output directory"),
    bitrate: Optional[str] = typer.Option(None, help="Target video bitrate"),
    delete_original: bool = typer.Option(False, "-d", "--delete-original", help="Delete original files after success"),
    overwrite: bool = typer.Option(False, "-o", "--overwrite", help="Force overwrite destination")
):
    """Batch convert MP4s to AV1 (Auto-detects AMD GPU vs CPU)."""
    check_ffmpeg()
    convert_videos(input_path, output_dir, bitrate, delete_original, overwrite)

if __name__ == "__main__":
    app()