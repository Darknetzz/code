"""ffmpeg / ffmpegthumbnailer thumbnail generation for pygallery.

Stdlib only; soft-fails when neither tool is on PATH so galleries still build.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from _core import IMG_EXTS, VIDEO_EXTS

THUMB_SIZE = 480
DEFAULT_WORKERS = 6


def tools_available() -> bool:
    return shutil.which("ffmpeg") is not None or shutil.which("ffmpegthumbnailer") is not None


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def _media_digest(media: Path) -> str:
    return hashlib.sha1(str(media.resolve()).encode()).hexdigest()[:16]


def thumb_path_for(media: Path, thumbs_dir: Path) -> Path:
    return thumbs_dir / f"{_media_digest(media)}.jpg"


def duration_cache_path(media: Path, thumbs_dir: Path) -> Path:
    return thumbs_dir / f"{_media_digest(media)}.dur"


def thumb_is_fresh(media: Path, thumb: Path) -> bool:
    """True when ``thumb`` exists and is at least as new as ``media``."""
    try:
        return thumb.exists() and thumb.stat().st_mtime >= media.stat().st_mtime
    except OSError:
        return False


def media_needing_thumbs(media_paths: list[Path], thumbs_dir: Path) -> list[Path]:
    """Return media files that are missing a fresh cached thumbnail."""
    return [
        media for media in media_paths
        if not thumb_is_fresh(media, thumb_path_for(media, thumbs_dir))
    ]


def probe_duration(media: Path) -> float | None:
    """Return media duration in seconds via ffprobe, or ``None`` on failure."""
    if not ffprobe_available():
        return None
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(media),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        value = float(proc.stdout.strip())
        if value > 0 and value == value:  # not NaN
            return value
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None
    return None


def read_cached_duration(media: Path, thumbs_dir: Path) -> float | None:
    cache = duration_cache_path(media, thumbs_dir)
    if not thumb_is_fresh(media, cache):
        return None
    try:
        return float(cache.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def write_cached_duration(media: Path, thumbs_dir: Path, seconds: float) -> None:
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    cache = duration_cache_path(media, thumbs_dir)
    tmp = cache.with_suffix(".dur.tmp")
    tmp.write_text(f"{seconds:.3f}\n", encoding="utf-8")
    tmp.replace(cache)


def _duration_worker(media: Path, thumbs_dir: Path) -> tuple[Path, float | None]:
    cached = read_cached_duration(media, thumbs_dir)
    if cached is not None:
        return media, cached
    seconds = probe_duration(media)
    if seconds is not None:
        try:
            write_cached_duration(media, thumbs_dir, seconds)
        except OSError:
            pass
    return media, seconds


def ensure_durations(
    media_paths: list[Path],
    thumbs_dir: Path,
    *,
    workers: int = DEFAULT_WORKERS,
) -> dict[Path, float]:
    """Probe (and cache) durations for video files. Returns path → seconds."""
    videos = [p for p in media_paths if p.suffix.lower() in VIDEO_EXTS]
    result: dict[Path, float] = {}
    if not videos:
        return result
    if not ffprobe_available():
        print("ffprobe not on PATH — video durations will be omitted.", flush=True)
        return result

    thumbs_dir.mkdir(parents=True, exist_ok=True)
    pending = [p for p in videos if read_cached_duration(p, thumbs_dir) is None]
    # Fill already-cached first
    for p in videos:
        cached = read_cached_duration(p, thumbs_dir)
        if cached is not None:
            result[p] = cached

    if not pending:
        return result

    print(f"Probing duration for {len(pending)} video(s)…", flush=True)
    workers = max(1, workers)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_duration_worker, media, thumbs_dir): media
            for media in pending
        }
        done = 0
        total = len(futures)
        for fut in as_completed(futures):
            media, seconds = fut.result()
            done += 1
            if seconds is not None:
                result[media] = seconds
            if done % 25 == 0 or done == total:
                print(f"[{done}/{total}] durations…", flush=True)
    return result


def _is_image(path: Path) -> bool:
    return path.suffix.lower() in IMG_EXTS


def make_thumb(media: Path, thumb: Path) -> tuple[Path, str]:
    """Create or reuse a JPEG thumbnail. Returns ``(media, status)``."""
    if thumb_is_fresh(media, thumb):
        return media, "cached"

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
