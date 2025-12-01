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

# Store detected encoder info
# Structure: {"encoder": "name", "codec": "av1|hevc", "hw_type": "nvidia|amd|cpu"}
ACTIVE_ENCODER = None

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
    """
    try:
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
        
        # Fallback: Calculate from duration/size
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
            return int((size * 8 / duration) * 0.9)
            
    except Exception as e:
        cprint(f"Could not calculate input bitrate: {e}", "warning")
    
    return None

# ============================================================================ #
#                       FUNCTION: check_encoder_support                        #
# ============================================================================ #
def check_encoder_support(encoder_name):
    """
    Checks if a specific FFmpeg encoder is usable (drivers installed).
    """
    try:
        # Use 720p test to satisfy RDNA3 and newer NVENC requirements
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
def needs_transcoding(file_path):
    try:
        cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
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

    if not needs_transcoding(input_path):
        cprint("Skipping (No Transcoding Needed): " + filename, "info")
        return

    if output_dir is None:
        output_dir = os.path.dirname(input_path)
        # Naming suffix
        suffix = f"-{ACTIVE_ENCODER['codec'].upper()}.mkv"
        output_name = os.path.splitext(filename)[0] + suffix
    else:
        os.makedirs(output_dir, exist_ok=True)
        suffix = f"_{ACTIVE_ENCODER['codec']}.mkv"
        output_name = os.path.splitext(filename)[0] + suffix
    
    output_path = os.path.join(output_dir, output_name)
    temp_output = f"{output_path}.temp.mkv"

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        if not overwrite:
            if input(f"File exists: {output_path}. Delete? [y/N]: ").lower() not in ("y", "yes"): return

    # --- CALCULATE TARGET BITRATE ---
    target_bitrate_int = 0
    if bitrate:
        if isinstance(bitrate, str) and bitrate.lower().endswith('m'):
             target_bitrate_int = int(bitrate[:-1]) * 1000000
        else:
             target_bitrate_int = int(bitrate)
    else:
        input_bitrate = get_input_bitrate(input_path)
        if input_bitrate:
            target_bitrate_int = int(input_bitrate * 0.5) # Force 50%
            cprint(f"Source: {input_bitrate/1000000:.2f}M -> Target: {target_bitrate_int/1000000:.2f}M", "info")
        else:
            cprint("Bitrate unknown. Using 2M fallback.", "warning")
            target_bitrate_int = 2000000

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
        "-maxrate", str(int(target_bitrate_int * 1.2)),
        "-bufsize", str(int(target_bitrate_int * 2))
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

    # Audio: 64k Opus
    command.extend(["-c:a", "libopus", "-b:a", "64k", "-ac", "2", temp_output])

    cprint(f"Converting: {filename} using {encoder_name}", "info")
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
    """Universal Video Compressor (AMD/NVIDIA/CPU) - Force 50% size reduction."""
    check_ffmpeg()
    convert_videos(input_path, output_dir, bitrate, delete_original, overwrite)

if __name__ == "__main__":
    app()