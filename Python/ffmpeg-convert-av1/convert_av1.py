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

import os
import subprocess
import argparse
import shutil
import sys
from rich.console import Console

console = Console()

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
        sys.exit(1)

# ============================================================================ #
#                        FUNCTION: maybe_delete_original                       #
# ============================================================================ #
def maybe_delete_original(original_path, auto_delete=False):
    try:
        if auto_delete:
            os.remove(original_path)
            cprint(f"Deleted original: {original_path}")
            return
        resp = input(f"Delete original file?\n{original_path}\n[y/N/a]: ").strip().lower()
        if resp in ("y", "yes"):
            os.remove(original_path)
            cprint("Original deleted.", "success")
        elif resp in ("a", "all"):
            os.remove(original_path)
            cprint("Original deleted.", "success")
            return True  # Signal to enable auto_delete for remaining files
        else:
            cprint("Kept original.", "info")
    except Exception as e:
        cprint(f"Could not delete {original_path}: {e}", "warning")
    return False

# ============================================================================ #
#                         FUNCTION: convert_single_file                        #
# ============================================================================ #
def convert_single_file(input_path, output_dir=None, bitrate=None, delete_original=False):
    filename = os.path.basename(input_path)
    
    if output_dir is None:
        output_dir = os.path.dirname(input_path)
        output_name = os.path.splitext(filename)[0] + "-AV1.mkv"
    else:
        os.makedirs(output_dir, exist_ok=True)
        output_name = os.path.splitext(filename)[0] + "_av1.mkv"
    
    output_path = os.path.join(output_dir, output_name)

    # Check file size before conversion
    file_size = os.path.getsize(input_path)
    if file_size == 0:
        cprint(f"Skipping zero-byte file: {filename}", "warning")
        return

    command = [
        "ffmpeg",
        "-i", input_path,
        "-vf", "scale='min(1920,iw)':'min(1080,ih)':force_original_aspect_ratio=decrease,format=yuv420p,scale=in_range=limited:out_range=limited",
        "-c:v", "av1_amf",
        "-usage", "transcoding",
        "-quality", "speed",
        "-rc", "vbr_peak",
        "-qp", "40",
        "-c:a", "libopus",
        "-b:a", "64k",
        "-ac", "1",
        output_path
    ]

    if bitrate is not None:
        command.extend(["-b:v", bitrate])
    else:
        command.extend(["-qp", "28"])

    command.append(output_path)

    cprint(f"Command: {' '.join(command)}", "info")

    cprint(f"Converting: {filename}", "info")
    subprocess.run(command, check=True)

    # Only attempt deletion if conversion succeeded
    if os.path.exists(output_path):
        new_file_size = os.path.getsize(output_path)
        cprint(f"Converted {filename}: {file_size / (1024**2):.2f} MB -> {new_file_size / (1024**2):.2f} MB", "success")
        
        if file_size <= new_file_size:
            cprint(f"Converted file is not smaller than original for {filename}. Keeping original.", "warning")
        else:
            maybe_delete_original(input_path, auto_delete=delete_original)
    else:
        cprint(f"Conversion failed for {filename}. Output file '{output_path}' does not exist.", "error")

# ============================================================================ #
#                           FUNCTION: convert_videos                           #
# ============================================================================ #
def convert_videos(input_path, output_dir=None, bitrate=None, delete_original=False):
    # Auto-detect if input is a file or directory
    if os.path.isfile(input_path):
        if not input_path.lower().endswith(".mp4"):
            cprint(f"File '{input_path}' is not an MP4 file.", "error")
            sys.exit(1)
        convert_single_file(input_path, output_dir, bitrate, delete_original)
    elif os.path.isdir(input_path):
        if output_dir is None:
            output_dir = input_path
        else:
            os.makedirs(output_dir, exist_ok=True)

        for filename in os.listdir(input_path):
            if filename.lower().endswith(".mp4"):
                file_path = os.path.join(input_path, filename)
                convert_single_file(file_path, output_dir, bitrate, delete_original)
    else:
        cprint(f"{input_path} is neither a valid file nor directory.", "error")
        sys.exit(1)

    cprint("All conversions complete.", "success")

# ============================================================================ #
#                                FUNCTION: main                                #
# ============================================================================ #
def main():
    parser = argparse.ArgumentParser(description="Batch convert MP4s to AV1 using AMD GPU.")
    parser.add_argument("input_path", help="Path to input file or directory containing .mp4 files")
    parser.add_argument("output_dir", nargs="?", default=None, help="Path to output directory for converted files (optional)")
    parser.add_argument("--bitrate", default=None, help="Target video bitrate (default: same as source)")
    parser.add_argument("--delete-original", "-d", action="store_true",
                        help="Delete original files after successful conversion without prompting",
                        default=False)

    args = parser.parse_args()

    check_ffmpeg()
    convert_videos(args.input_path, args.output_dir, args.bitrate, args.delete_original)

if __name__ == "__main__":
    main()