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

# Global flag for Hardware Codec
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
#                      FUNCTION: get_input_bitrate                             #
# ============================================================================ #
def get_input_bitrate(file_path):
    """
    Returns the bitrate of the video stream in bits/s.
    Tries metadata first, calculates from size/duration if metadata fails.
    """
    try:
        # Method 1: Ask FFprobe for stream bitrate
        cmd = [
            "ffprobe", "-v", "error", 
            "-select_streams", "v:0",
            "-show_entries", "stream=bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=1", 
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        val = result.stdout.strip()
        if val.isdigit():
            return int(val)
        
        # Method 2: Calculate from file size and duration (Fallback)
        cmd_dur = [
            "ffprobe", "-v", "error", 
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", 
            file_path
        ]
        result_dur = subprocess.run(cmd_dur, capture_output=True, text=True)
        duration = float(result_dur.stdout.strip())
        size = os.path.getsize(file_path)
        
        if duration > 0:
            # size (bytes) * 8 / duration (sec) = bits/sec
            # Multiply by 0.9 to account for audio/container overhead roughly
            return int((size * 8 / duration) * 0.9)
            
    except Exception as e:
        cprint(f"Could not calculate input bitrate: {e}", "warning")
    
    return None

# ============================================================================ #
#                       FUNCTION: check_hardware_encoder                       #
# ============================================================================ #
def check_hardware_encoder(encoder_name):
    try:
        # Use 720p test to satisfy RDNA3 requirement
        cmd = [
            "ffmpeg", "-v", "quiet", "-f", "lavfi",
            "-i", "testsrc=size=1280x720:rate=30:duration=0.1",
            "-c:v", encoder_name, "-f", "null", "-"
        ]
        return subprocess.run(cmd, check=False).returncode == 0
    except Exception:
        return False

# ============================================================================ #
#                            FUNCTION: check_ffmpeg                            #
# ============================================================================ #
def check_ffmpeg():
    global HARDWARE_CODEC_TYPE
    if shutil.which("ffmpeg") is None:
        cprint("ffmpeg is not found.", "error")
        raise typer.Exit(code=1)
    
    cprint("Detecting Hardware Encoder Support...", "info")
    if check_hardware_encoder("av1_amf"):
        HARDWARE_CODEC_TYPE = "av1"
        cprint("Hardware Found: AMD AV1 (`av1_amf`). Using RX 7000+ Engine.", "success")
    elif check_hardware_encoder("hevc_amf"):
        HARDWARE_CODEC_TYPE = "hevc"
        cprint("Hardware Found: AMD HEVC (`hevc_amf`). Fallback mode.", "success")
    else:
        HARDWARE_CODEC_TYPE = None
        cprint("No AMD Hardware. Using CPU (`libsvtav1`).", "warning")

# ============================================================================ #
#                          FUNCTION: needs_transcoding                         #
# ============================================================================ #
def needs_transcoding(file_path):
    try:
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                codec = stream.get('codec_name')
                if HARDWARE_CODEC_TYPE == "av1" and codec == 'av1': return False
                if HARDWARE_CODEC_TYPE == "hevc" and codec in ['hevc', 'h265']: return False
                return True
        return False
    except Exception:
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
            return True
    except Exception as e:
        cprint(f"Could not delete {original_path}: {e}", "warning")
    return False

# ============================================================================ #
#                         FUNCTION: convert_single_file                        #
# ============================================================================ #
def convert_single_file(input_path, output_dir=None, bitrate=None, delete_original=False, overwrite=False):
    filename = os.path.basename(input_path)
    
    if not input_path.lower().endswith((".mp4", ".mkv")): return

    if not needs_transcoding(input_path): return

    if output_dir is None:
        output_dir = os.path.dirname(input_path)
        suffix = "-AV1.mkv" if HARDWARE_CODEC_TYPE != "hevc" else "-HEVC.mkv"
        output_name = os.path.splitext(filename)[0] + suffix
    else:
        os.makedirs(output_dir, exist_ok=True)
        suffix = "_av1.mkv" if HARDWARE_CODEC_TYPE != "hevc" else "_hevc.mkv"
        output_name = os.path.splitext(filename)[0] + suffix
    
    output_path = os.path.join(output_dir, output_name)
    temp_output = f"{output_path}.temp.mkv"

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        if not overwrite:
            if input(f"File exists: {output_path}. Delete? [y/N]: ").lower() not in ("y", "yes"): return

    # --- CALCULATE TARGET BITRATE ---
    target_bitrate_int = 0
    if bitrate:
        # User manual override
        if isinstance(bitrate, str) and bitrate.lower().endswith('m'):
             target_bitrate_int = int(bitrate[:-1]) * 1000000
        else:
             target_bitrate_int = int(bitrate)
    else:
        # AUTO-REDUCTION MODE
        input_bitrate = get_input_bitrate(input_path)
        if input_bitrate:
            # Force 50% reduction
            target_bitrate_int = int(input_bitrate * 0.5)
            cprint(f"Source: {input_bitrate/1000000:.2f} Mbps -> Target (50%): {target_bitrate_int/1000000:.2f} Mbps", "info")
        else:
            cprint("Could not detect input bitrate. Fallback to default low bitrate (2M).", "warning")
            target_bitrate_int = 2000000 # 2Mbps fallback

    # --- BUILD COMMAND ---
    pix_fmt = "nv12" if HARDWARE_CODEC_TYPE else "yuv420p"
    
    command = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale='min(1920,iw)':-2:force_original_aspect_ratio=decrease,format={pix_fmt}",
        "-movflags", "+faststart",
    ]

    # VBR Settings for Hardware
    # To enforce size, we use -b:v (Target) and -maxrate (Peak)
    # Hardware encoders respect these flags better than CQP for sizing.
    bitrate_args = [
        "-b:v", str(target_bitrate_int),
        "-maxrate", str(int(target_bitrate_int * 1.2)), # Allow small peaks
        "-bufsize", str(int(target_bitrate_int * 2))
    ]

    if HARDWARE_CODEC_TYPE == "av1":
        command.extend(["-c:v", "av1_amf", "-usage", "transcoding", "-quality", "balanced", "-profile:v", "main"])
        command.extend(bitrate_args)
        
    elif HARDWARE_CODEC_TYPE == "hevc":
        command.extend(["-c:v", "hevc_amf", "-usage", "transcoding", "-quality", "balanced", "-tag:v", "hvc1"])
        command.extend(bitrate_args)
        
    else:
        # CPU Fallback
        command.extend(["-c:v", "libsvtav1", "-preset", "8", "-g", "240"])
        # SVT-AV1 prefers CRF, but for forced sizing we can use VBR too. 
        # But to be safe on CPU, let's map bitrate to a CRF estimate or use VBR.
        # Let's stick to VBR to guarantee the 50% cut.
        command.extend(bitrate_args)

    # Audio: 64k Opus
    command.extend(["-c:a", "libopus", "-b:a", "64k", "-ac", "2", temp_output])

    cprint(f"Converting: {filename}", "info")
    result = subprocess.run(command, check=False)

    if result.returncode == 0:
        try:
            if os.path.exists(temp_output):
                os.replace(temp_output, output_path)
                file_size = os.path.getsize(input_path)
                new_file_size = os.path.getsize(output_path)
                cprint(f"Done: {file_size / (1024**2):.2f} MB -> {new_file_size / (1024**2):.2f} MB", "success")
                
                if file_size <= new_file_size:
                    cprint("Warning: File grew larger! (Entropy issue).", "warning")
                else:
                    if maybe_delete_original(input_path, auto_delete=delete_original):
                        delete_original = True
            else:
                cprint("Error: Temp file missing!", "error")
        except OSError as e:
            cprint(f"Error swapping files: {e}", "error")
    else:
        cprint(f"Conversion failed (Code: {result.returncode})", "error")
        if os.path.exists(temp_output): os.remove(temp_output)

    return delete_original

# ============================================================================ #
#                           FUNCTION: convert_videos                           #
# ============================================================================ #
def convert_videos(input_path, output_dir=None, bitrate=None, delete_original=False, overwrite=False):
    if os.path.isfile(input_path):
        convert_single_file(input_path, output_dir, bitrate, delete_original, overwrite)
    elif os.path.isdir(input_path):
        if output_dir is None: output_dir = input_path
        else: os.makedirs(output_dir, exist_ok=True)
        for filename in os.listdir(input_path):
            if filename.lower().endswith((".mp4", ".mkv")):
                res = convert_single_file(os.path.join(input_path, filename), output_dir, bitrate, delete_original, overwrite)
                if isinstance(res, bool) and res: delete_original = True
    else:
        cprint("Invalid path.", "error")

@app.command()
def main(
    input_path: str = typer.Argument(..., help="Path to input"),
    output_dir: Optional[str] = typer.Argument(None, help="Output dir"),
    bitrate: Optional[str] = typer.Option(None, help="Override bitrate"),
    delete_original: bool = typer.Option(False, "-d", "--delete-original"),
    overwrite: bool = typer.Option(False, "-o", "--overwrite")
):
    """Force 50% size reduction on AV1/HEVC Hardware."""
    check_ffmpeg()
    convert_videos(input_path, output_dir, bitrate, delete_original, overwrite)

if __name__ == "__main__":
    app()