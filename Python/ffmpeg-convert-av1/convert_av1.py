# ============================================================================ #
#                                convert_av1.py                                #
# ============================================================================ #
# usage:
# python convert_av1.py "C:\Videos\Input" "C:\Videos\Output"
# python convert_av1.py "C:\Videos\video.mp4" --delete-original

import os, subprocess, shutil, sys, json
from typing import Optional
from rich.console import Console
import typer

console = Console()
app = typer.Typer()

# Global flag to store which HARDWARE codec is available
# Values: "av1", "hevc", or None (CPU)
HARDWARE_CODEC_TYPE = None 

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
def check_hardware_encoder(encoder_name):
    """
    Checks if a specific FFmpeg encoder is available and working.
    """
    try:
        # We use 1280x720 because many GPUs fail to initialize on tiny (64x64) resolutions
        cmd = [
            "ffmpeg",
            "-v", "quiet",
            "-f", "lavfi",
            "-i", "testsrc=size=1280x720:rate=30:duration=0.1",
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
    global HARDWARE_CODEC_TYPE
    
    if shutil.which("ffmpeg") is None:
        cprint("ffmpeg is not found in your system PATH.", "error")
        raise typer.Exit(code=1)
    
    cprint("Detecting Hardware Encoder Support...", "info")
    
    # 1. Try AV1 GPU (Best/Newest) - RX 7000+ Series
    if check_hardware_encoder("av1_amf"):
        HARDWARE_CODEC_TYPE = "av1"
        cprint("Hardware Found: AMD AV1 (`av1_amf`). Using RX 7000+ Engine.", "success")
        
    # 2. Try HEVC GPU (Fast & Compatible) - RX 6000/5000 Series
    elif check_hardware_encoder("hevc_amf"):
        HARDWARE_CODEC_TYPE = "hevc"
        cprint("Hardware Found: AMD HEVC/H.265 (`hevc_amf`).", "success")
        cprint("Note: AV1 hardware encode failed, using HEVC fallback.", "info")
        
    # 3. Fallback to CPU
    else:
        HARDWARE_CODEC_TYPE = None
        cprint("No AMD Hardware Encoder detected. Falling back to CPU (`libsvtav1`).", "warning")

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
                
                # If we are targeting AV1, skip if already AV1
                if HARDWARE_CODEC_TYPE == "av1" or HARDWARE_CODEC_TYPE is None:
                    if codec == 'av1':
                        print(f"Skipping {file_path}: Already AV1.")
                        return False
                        
                # If we are targeting HEVC, skip if already HEVC
                if HARDWARE_CODEC_TYPE == "hevc":
                    if codec in ['hevc', 'h265']:
                        print(f"Skipping {file_path}: Already HEVC/H.265.")
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
        return

    if output_dir is None:
        output_dir = os.path.dirname(input_path)
        # Naming convention based on codec
        suffix = "-AV1.mkv" if HARDWARE_CODEC_TYPE != "hevc" else "-HEVC.mkv"
        output_name = os.path.splitext(filename)[0] + suffix
    else:
        os.makedirs(output_dir, exist_ok=True)
        suffix = "_av1.mkv" if HARDWARE_CODEC_TYPE != "hevc" else "_hevc.mkv"
        output_name = os.path.splitext(filename)[0] + suffix
    
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
    #                       BUILDING THE COMMAND                               #
    # ------------------------------------------------------------------------ #
    
    # DETERMINE PIXEL FORMAT
    # AMD AMF (GPU) requires 'nv12'
    # SVT-AV1 (CPU) works best with 'yuv420p'
    pix_fmt = "nv12" if HARDWARE_CODEC_TYPE else "yuv420p"
    
    command = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", f"scale='min(1920,iw)':-2:force_original_aspect_ratio=decrease,format={pix_fmt}",
        "-movflags", "+faststart",
    ]

    # --- Codec Selection & Metadata ---
    if HARDWARE_CODEC_TYPE == "av1":
        # === TIER 1: AV1 GPU (RX 7000+) ===
        command.extend([
            "-c:v", "av1_amf",
            "-usage", "transcoding",
            "-quality", "balanced",
            "-profile:v", "main",
            "-metadata", "major_brand=mp42",
            "-metadata", "compatible_brands=mp42av01iso2mp41",
        ])
    elif HARDWARE_CODEC_TYPE == "hevc":
        # === TIER 2: HEVC GPU (RX 6000/5000) ===
        command.extend([
            "-c:v", "hevc_amf",
            "-usage", "transcoding",
            "-quality", "balanced",
            "-profile:v", "main",
            "-tag:v", "hvc1", 
        ])
    else:
        # === TIER 3: AV1 CPU (Universal) ===
        command.extend([
            "-c:v", "libsvtav1",
            "-preset", "8",
            "-g", "240",
            "-metadata", "major_brand=mp42",
            "-metadata", "compatible_brands=mp42av01iso2mp41",
        ])

    # --- Rate Control (Max Compression Strategy) ---
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
                target_bitrate_int = 0
        else:
            target_bitrate_int = bitrate

    if target_bitrate_int > 0:
        # User defined bitrate
        max_rate = int(target_bitrate_int * 1.5)
        buf_size = int(target_bitrate_int * 2)
        command.extend([
            "-b:v", str(target_bitrate_int),
            "-maxrate", str(max_rate),
            "-bufsize", str(buf_size)
        ])
    else:
        # MAX COMPRESSION AUTO-SETTINGS (CQP 45)
        if HARDWARE_CODEC_TYPE == "av1":
            cprint("GPU AV1 Mode: Using CQP 45 (Aggressive)", "info")
            command.extend(["-rc", "cqp", "-qp_i", "45", "-qp_p", "45"])
            
        elif HARDWARE_CODEC_TYPE == "hevc":
            cprint("GPU HEVC Mode: Using CQP 35 (Aggressive)", "info")
            command.extend(["-rc", "cqp", "-qp_i", "35", "-qp_p", "35"])
            
        else:
            cprint("CPU AV1 Mode: Using CRF 45 (Aggressive)", "info")
            command.extend(["-crf", "45"])

    # --- Audio Encoder (Reduced to 64k for size) ---
    command.extend([
        "-c:a", "libopus",
        "-b:a", "64k",
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
                    cprint(f"Warning: Output is larger or same size.", "warning")
                else:
                    enable_auto = maybe_delete_original(input_path, auto_delete=delete_original)
                    if enable_auto:
                        delete_original = True
            else:
                cprint(f"Error: Temp file missing!", "error")
        except OSError as e:
            cprint(f"Error swapping files: {e}", "error")
    else:
        cprint(f"Conversion failed (Error: {result.returncode})", "error")
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
    """Batch convert video to optimized formats (Auto-detects AV1/HEVC Hardware)."""
    check_ffmpeg()
    convert_videos(input_path, output_dir, bitrate, delete_original, overwrite)

if __name__ == "__main__":
    app()