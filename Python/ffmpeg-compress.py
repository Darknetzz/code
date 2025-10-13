#!/usr/bin/env python3
"""
Batch transcode videos to 720p30 using AV1 (libsvtav1) or H.265/HEVC (libx265 or hevc_nvenc).

Features
- Recursively scans an input folder for common video files
- Rescales to 720p with preserved aspect ratio and avoids upscaling tiny sources
- Forces 30 fps (optional) or keeps source VFR
- Chooses sensible defaults for AV1 or HEVC
- Copies audio by default if compatible, else re-encodes (Opus for MKV, AAC for MP4)
- Skips files that already have a matching output
- Parallel processing option

Requirements
- ffmpeg must be installed and available in PATH

Examples
# AV1, constant quality CRF 32, preset 6
python batch_transcode_720p.py -i "D:/Videos" -o "D:/Encoded" --codec av1 --crf 32 --preset 6

# HEVC, constant quality CRF 24, preset medium, MP4 outputs
python batch_transcode_720p.py -i "/mnt/media" -o "/mnt/media/h265" --codec hevc --crf 24 --preset medium --container mp4

# HEVC with NVIDIA NVENC (fast)
python batch_transcode_720p.py -i "/mnt/media" -o "/mnt/media/h265" --codec hevc_nvenc --cq 23 --preset p5 --container mp4

"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# Common video extensions to scan
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".m4v", ".avi", ".webm", ".ts", ".m2ts"}


def which(cmd: str) -> Optional[str]:
    """Return full path to an executable or None if not found."""
    from shutil import which as _which
    return _which(cmd)


def build_filter(vfr: bool, force_30fps: bool) -> str:
    # Scale: limit height to 720, keep AR, do not upscale
    scale = "scale=-2:720:force_original_aspect_ratio=decrease"
    if force_30fps:
        fps = "fps=30"
        vf = f"{scale},{fps}"
    else:
        vf = scale
    return vf


def out_name(in_path: Path, out_dir: Path, container: str, suffix: str) -> Path:
    base = in_path.stem + suffix
    ext = ".mkv" if container.lower() == "mkv" else ".mp4"
    return out_dir / f"{base}{ext}"


def build_cmd(
    src: Path,
    dst: Path,
    codec: str,
    crf: Optional[int],
    cq: Optional[int],
    preset: str,
    container: str,
    keep_vfr: bool,
    copy_audio: bool,
) -> List[str]:
    vf = build_filter(vfr=keep_vfr, force_30fps=not keep_vfr)

    # Container-specific audio defaults
    if copy_audio:
        audio_args = ["-c:a", "copy"]
    else:
        if container.lower() == "mkv":
            audio_args = ["-c:a", "libopus", "-b:a", "112k"]
        else:
            audio_args = ["-c:a", "aac", "-b:a", "128k"]

    common = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-vf", vf,
        "-pix_fmt", "yuv420p",
    ]

    if codec == "av1":
        v_args = [
            "-c:v", "libsvtav1",
            "-crf", str(crf if crf is not None else 32),
            "-b:v", "0",
            "-preset", str(preset),
        ]
        # Recommend MKV for AV1
    elif codec == "hevc":
        v_args = [
            "-c:v", "libx265",
            "-crf", str(crf if crf is not None else 24),
            "-preset", str(preset),
        ]
    elif codec == "hevc_nvenc":
        v_args = [
            "-c:v", "hevc_nvenc",
            "-rc", "vbr",
            "-b:v", "0",
            "-cq", str(cq if cq is not None else 23),
            "-preset", str(preset),  # e.g., p5
        ]
    else:
        raise ValueError(f"Unsupported codec: {codec}")

    # Faststart for MP4 streaming friendliness
    tail = ["-movflags", "+faststart"] if container.lower() == "mp4" else []

    return [*common, *v_args, *audio_args, *tail, str(dst)]


def transcode_one(args) -> None:
    src: Path = args[0]
    dst: Path = args[1]
    cmd: List[str] = args[2]
    dry_run: bool = args[3]

    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        print(f"[skip] {src} -> {dst} (already exists)")
        return

    print(f"[run ] {' '.join(shlex.quote(c) for c in cmd)}")
    if dry_run:
        return

    try:
        subprocess.run(cmd, check=True)
        print(f"[done] {dst}")
    except subprocess.CalledProcessError as e:
        print(f"[fail] {src} -> {dst}: {e}")


def gather_inputs(root: Path) -> List[Path]:
    files: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            files.append(p)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch transcode videos to 720p using AV1 or HEVC")
    parser.add_argument("-i", "--input", required=True, type=Path, help="Input folder")
    parser.add_argument("-o", "--output", required=True, type=Path, help="Output folder")
    parser.add_argument("--codec", choices=["av1", "hevc", "hevc_nvenc"], default="hevc",
                        help="Video codec: av1=libsvtav1, hevc=libx265, hevc_nvenc=NVIDIA NVENC HEVC")
    parser.add_argument("--container", choices=["mkv", "mp4"], default="mkv",
                        help="Output container format")
    parser.add_argument("--crf", type=int, help="Quality factor for libsvtav1/libx265 (lower=bigger)")
    parser.add_argument("--cq", type=int, help="Quality for hevc_nvenc (lower=bigger)")
    parser.add_argument("--preset", default="6", help="Encoder preset (libsvtav1 numeric 1-13, libx265 string like 'medium', NVENC p1..p7)")
    parser.add_argument("--copy-audio", action="store_true", help="Copy audio streams instead of re-encoding")
    parser.add_argument("--keep-vfr", action="store_true", help="Keep source frame rate (don’t force 30fps)")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them")

    args = parser.parse_args()

    if which("ffmpeg") is None:
        print("ffmpeg not found in PATH. Please install ffmpeg and try again.")
        return 1

    inputs = gather_inputs(args.input)
    if not inputs:
        print("No input videos found.")
        return 0

    suffix = {
        "av1": ".av1",
        "hevc": ".h265",
        "hevc_nvenc": ".h265",
    }[args.codec]

    tasks = []
    for src in inputs:
        dst = out_name(src, args.output, args.container, suffix)
        cmd = build_cmd(
            src=src,
            dst=dst,
            codec=args.codec,
            crf=args.crf,
            cq=args.cq,
            preset=str(args.preset),
            container=args.container,
            keep_vfr=args.keep_vfr,
            copy_audio=args.copy_audio,
        )
        tasks.append((src, dst, cmd, args.dry_run))

    # Parallel execution
    workers = max(1, int(args.workers))
    if workers == 1:
        for t in tasks:
            transcode_one(t)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(transcode_one, tasks))

    return 0


if __name__ == "__main__":
    sys.exit(main())
