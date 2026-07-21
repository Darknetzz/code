"""ffmpeg / ffmpegthumbnailer thumbnail generation for pygallery.

Stdlib only; soft-fails when neither tool is on PATH so galleries still build.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from _core import IMG_EXTS

THUMB_SIZE = 480
DEFAULT_WORKERS = 6


def tools_available() -> bool:
    return shutil.which("ffmpeg") is not None or shutil.which("ffmpegthumbnailer") is not None


def thumb_path_for(media: Path, thumbs_dir: Path) -> Path:
    digest = hashlib.sha1(str(media.resolve()).encode()).hexdigest()[:16]
    return thumbs_dir / f"{digest}.jpg"


def _is_image(path: Path) -> bool:
    return path.suffix.lower() in IMG_EXTS


def make_thumb(media: Path, thumb: Path) -> tuple[Path, str]:
    """Create or reuse a JPEG thumbnail. Returns ``(media, status)``."""
    try:
        if thumb.exists() and thumb.stat().st_mtime >= media.stat().st_mtime:
            return media, "cached"
    except OSError:
        pass

    thumb.parent.mkdir(parents=True, exist_ok=True)
    tmp = thumb.with_suffix(".tmp.jpg")

    if _is_image(media):
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(media),
                    "-vf",
                    f"scale='min({THUMB_SIZE},iw)':-1",
                    "-frames:v",
                    "1",
                    "-q:v",
                    "4",
                    str(tmp),
                ],
                check=True,
                capture_output=True,
            )
            tmp.replace(thumb)
            return media, "ok"
        except Exception as e:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            return media, f"fail:{e}"

    try:
        subprocess.run(
            [
                "ffmpegthumbnailer",
                "-i",
                str(media),
                "-o",
                str(tmp),
                "-s",
                str(THUMB_SIZE),
                "-q",
                "6",
                "-f",
            ],
            check=True,
            capture_output=True,
        )
        tmp.replace(thumb)
        return media, "ok"
    except Exception as e:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    "5",
                    "-i",
                    str(media),
                    "-frames:v",
                    "1",
                    "-q:v",
                    "4",
                    str(tmp),
                ],
                check=True,
                capture_output=True,
            )
            tmp.replace(thumb)
            return media, "ffmpeg"
        except Exception:
            return media, f"fail:{e}"


def generate_thumbs(
    media_paths: list[Path],
    thumbs_dir: Path,
    *,
    workers: int = DEFAULT_WORKERS,
) -> tuple[dict[Path, Path], dict[str, int]]:
    """Generate thumbnails in parallel.

    Returns ``(media_path -> thumb_path, status_counts)``. Skips all work when
    neither ffmpeg nor ffmpegthumbnailer is available.
    """
    status_counts: dict[str, int] = {
        "ok": 0, "cached": 0, "ffmpeg": 0, "fail": 0, "skipped": 0,
    }
    thumb_map: dict[Path, Path] = {}

    if not media_paths:
        return thumb_map, status_counts

    if not tools_available():
        status_counts["skipped"] = len(media_paths)
        print(
            "No ffmpeg/ffmpegthumbnailer on PATH — skipping thumbnails.",
            flush=True,
        )
        return thumb_map, status_counts

    thumbs_dir.mkdir(parents=True, exist_ok=True)
    workers = max(1, workers)
    total = len(media_paths)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(make_thumb, media, thumb_path_for(media, thumbs_dir)): media
            for media in media_paths
        }
        done = 0
        for fut in as_completed(futures):
            media, status = fut.result()
            done += 1
            if status.startswith("fail"):
                status_counts["fail"] += 1
                print(f"[{done}/{total}] FAIL {media.name}: {status}", flush=True)
            else:
                key = status if status in status_counts else "ok"
                status_counts[key] += 1
                thumb_map[media] = thumb_path_for(media, thumbs_dir)
                if done % 25 == 0 or done == total:
                    print(f"[{done}/{total}] thumbs… ({status})", flush=True)

    return thumb_map, status_counts
