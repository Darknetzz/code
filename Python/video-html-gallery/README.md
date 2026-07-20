# video-html-gallery

Build a local dark-themed HTML gallery for **videos and images**, grouped by folder, with thumbnails, search, and sorting.

## Features

- Scans a media library recursively and groups files by top-level folder
- Generates thumbnails (videos via `ffmpegthumbnailer` / `ffmpeg`, images via `ffmpeg`)
- Dark HTML page with:
  - Search/filter (title, folder, or `video` / `image`)
  - Sort by name, date, or size (ascending / descending)
  - Folder jump links
- Interactive prompts for any arguments you omit
- Pure Python 3 stdlib (no `pip install`)

## Requirements

- Python 3.10+ (uses `list[str] | None` style hints)
- [`ffmpeg`](https://ffmpeg.org/) on `PATH`
- Optional but recommended for videos: [`ffmpegthumbnailer`](https://github.com/dirkvdb/ffmpegthumbnailer)

## Supported formats

| Kind | Extensions |
|------|------------|
| Video | `.mp4` `.mkv` `.mov` `.webm` `.avi` `.m4v` |
| Image | `.jpg` `.jpeg` `.png` `.webp` `.gif` `.bmp` `.avif` |

Folders named `_gallery` and `_inbox` are skipped while scanning.

## Usage

```bash
cd Python/video-html-gallery

# Show help
python3 build_gallery.py --help

# Interactive (prompts for missing values)
python3 build_gallery.py

# Non-interactive
python3 build_gallery.py /path/to/media/library
python3 build_gallery.py /path/to/media/library -o /path/to/output/_gallery
python3 build_gallery.py /path/to/media/library -j 8
```

### Arguments

| Argument | Description |
|----------|-------------|
| `library` | Root folder of media (usually one subfolder per group) |
| `-o` / `--output` | Gallery output directory (default: `<library>/_gallery`) |
| `-j` / `--workers` | Parallel thumbnail workers (default: `6`) |

## Output

Creates (by default under `<library>/_gallery/`):

```text
_gallery/
  index.html    # open this in a browser
  thumbs/       # generated JPEG thumbnails
```

Open `index.html` from a **local HTTP server** when possible. Opening via `file://` often breaks video seeking in Chromium-based browsers.

Example:

```bash
cd /path/to/media/library
python3 -m http.server 18923 --bind 127.0.0.1
# then visit http://127.0.0.1:18923/_gallery/index.html
```

For reliable scrubbing/seeking, the server should support HTTP `Range` requests. Python’s built-in `http.server` does **not** — use a Range-capable static server if you need that.

## Notes

- Thumbnail generation is incremental: unchanged files reuse cached thumbs in `thumbs/`
- Sort preference is stored in the browser (`localStorage`)
- This folder intentionally ships only the generator script — no sample media
