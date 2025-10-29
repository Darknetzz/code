r"""
# ============================================================================ #
#                                convert_av1.py                                #
# ============================================================================ #
# usage:
# python convert_av1.py "C:\Videos\Input" "C:\Videos\Output" --bitrate 8M
# python convert_av1.py "C:\Videos\Input" --bitrate 8M
# python convert_av1.py "C:\Videos\video.mp4" --bitrate 8M
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

def convert_single_file(input_path, output_dir=None, bitrate="5M"):
    filename = os.path.basename(input_path)
    
    if output_dir is None:
        output_dir = os.path.dirname(input_path)
        output_name = os.path.splitext(filename)[0] + "-AV1.mkv"
    else:
        os.makedirs(output_dir, exist_ok=True)
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

def convert_videos(input_path, output_dir=None, bitrate="5M"):
    # Auto-detect if input is a file or directory
    if os.path.isfile(input_path):
        if not input_path.lower().endswith(".mp4"):
            print(f"Error: {input_path} is not an MP4 file.")
            sys.exit(1)
        convert_single_file(input_path, output_dir, bitrate)
    elif os.path.isdir(input_path):
        if output_dir is None:
            output_dir = input_path
        else:
            os.makedirs(output_dir, exist_ok=True)

        for filename in os.listdir(input_path):
            if filename.lower().endswith(".mp4"):
                file_path = os.path.join(input_path, filename)
                
                if output_dir == input_path:
                    output_name = os.path.splitext(filename)[0] + "-AV1.mkv"
                else:
                    output_name = os.path.splitext(filename)[0] + "_av1.mkv"
                
                output_path = os.path.join(output_dir, output_name)

                command = [
                    "ffmpeg",
                    "-i", file_path,
                    "-c:v", "av1_amf",
                    "-b:v", bitrate,
                    output_path
                ]

                print(f"Converting: {filename}")
                subprocess.run(command, check=True)
    else:
        print(f"Error: {input_path} is neither a valid file nor directory.")
        sys.exit(1)

    print("✅ All conversions complete.")

def main():
    parser = argparse.ArgumentParser(description="Batch convert MP4s to AV1 using AMD GPU.")
    parser.add_argument("input_path", help="Path to input file or directory containing .mp4 files")
    parser.add_argument("output_dir", nargs="?", default=None, help="Path to output directory for converted files (optional)")
    parser.add_argument("--bitrate", default="5M", help="Target video bitrate (default: 5M)")

    args = parser.parse_args()

    check_ffmpeg()
    convert_videos(args.input_path, args.output_dir, args.bitrate)

if __name__ == "__main__":
    main()