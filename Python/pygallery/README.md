# pygallery

Generate a static HTML gallery from a directory tree of images and videos
(generic libraries or Snapchat data exports). Stdlib only; optional
`ffmpeg` / `ffmpegthumbnailer` for thumbnails.

## Features

- Recursive scan with folder tabs, year/month/type filters, text search, and
  sort by date / name / size
- Lightbox viewer (works over `file://` — no web server required)
- Optional parallel thumbnails via `ffmpegthumbnailer` (preferred for video)
  or `ffmpeg`
- Snapchat export mode: groups media + thumbnail + overlay, optional chat
  history enrichment

## Requirements

- Python 3.10+
- Optional: [`ffmpeg`](https://ffmpeg.org/) on `PATH`
- Optional but recommended for videos: [`ffmpegthumbnailer`](https://github.com/dirkvdb/ffmpegthumbnailer)

## Supported formats

| Kind | Extensions |
|------|------------|
| Image | `.jpg` `.jpeg` `.png` `.webp` `.gif` `.bmp` `.avif` |
| Video | `.mp4` `.mkv` `.mov` `.webm` `.avi` `.m4v` |

Skipped directory names include `gallery`, `_gallery`, `_inbox`, VCS folders,
and other common junk dirs.

## Usage (generic)

```powershell
cd Python/pygallery

# Interactive (Tab completes paths; left/right arrows edit the line)
python pygallery.py

# Non-interactive
python pygallery.py D:\Photos
python pygallery.py D:\Photos --title "My Photos"
python pygallery.py D:\Photos -o D:\Photos\gallery -j 8
python pygallery.py D:\Photos --no-thumbs
```

### Arguments

| Argument | Description |
|----------|-------------|
| `root` | Directory to scan (prompted if omitted) |
| `-o` / `--output` | Asset output dir (default: `<root>/gallery`) |
| `-j` / `--workers` | Parallel thumbnail workers (default: `6`) |
| `--no-thumbs` | Skip ffmpeg thumbnail generation |
| `--title` | Page title (default: `Media Gallery`) |

## Usage (Snapchat)

```powershell
python pygallery-snapchat.py
python pygallery-snapchat.py D:\Temp\Snapchat
python pygallery-snapchat.py --enrich
```

Snapchat mode uses export-provided thumbnails/overlays and does not run ffmpeg.

## Output

Writes into the scanned root:

```text
gallery.html          # open this in a browser
gallery/
  style.css
  app.js
  manifest.json
  thumbs/             # generated JPEGs (generic mode only)
```

Thumbnail generation is incremental: unchanged files reuse cached thumbs.

## Notes

- Sort preference is stored in the browser (`localStorage`)
- Opening via `file://` is supported. For better video seeking in Chromium,
  serve the library over HTTP with `Range` support (Python’s `http.server`
  does not support Range).
