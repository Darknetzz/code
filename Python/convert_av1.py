r"""
# ============================================================================ #
#                                convert_av1.py                                #
# ============================================================================ #
# usage:
# python convert_av1.py "C:\Videos\Input" "C:\Videos\Output" --bitrate 8M
# python convert_av1.py "C:\Videos\Input" --bitrate 8M
"""

import os
import subprocess
import argparse
import shutil
import sys

def check_ffmpeg():
    if shutil.which("ffmpeg") is None:
        print("Error: ffmpeg is not found in your system PATH.")
        sys.exit(1)

def convert_videos(input_dir, output_dir=None, bitrate="5M"):
    if output_dir is None:
        output_dir = input_dir
    else:
        os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".mp4"):
            input_path = os.path.join(input_dir, filename)
            
            if output_dir == input_dir:
                output_name = os.path.splitext(filename)[0] + "-AV1.mkv"
            else:
                output_name = os.path.splitext(filename)[0] + "_av1.mkv"
            
            output_path = os.path.join(output_dir, output_name)

            command = [
                "ffmpeg",
                "-i", input_path,
                "-c:v", "av1_amf",
                "-b:v", bitrate,
                output_path
            ]

            print(f"Converting: {filename}")
            subprocess.run(command, check=True)

    print("✅ All conversions complete.")

def main():
    parser = argparse.ArgumentParser(description="Batch convert MP4s to AV1 using AMD GPU.")
    parser.add_argument("input_dir", help="Path to input directory containing .mp4 files")
    parser.add_argument("output_dir", nargs="?", default=None, help="Path to output directory for converted files (optional)")
    parser.add_argument("--bitrate", default="5M", help="Target video bitrate (default: 5M)")

    args = parser.parse_args()

    check_ffmpeg()
    convert_videos(args.input_dir, args.output_dir, args.bitrate)

if __name__ == "__main__":
    main()