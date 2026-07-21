# pygallery

Generate a static HTML gallery from a directory tree of images and videos
(generic libraries or Snapchat data exports). Stdlib only; optional
`ffmpeg` / `ffmpegthumbnailer` for thumbnails.

## Features

- Recursive scan with folder tabs, year/month/type filters, text search, and
  sort by date / name / size
- Lightbox viewer (works over `file://` or HTTP)
- **Default:** starts a Range-capable HTTP server after building (LAN-friendly)
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
# Then serves on http://0.0.0.0:18923/gallery.html
python pygallery.py

# Build + serve
python pygallery.py D:\Photos

# Build only (no server)
python pygallery.py D:\Photos --no-serve

# Custom bind/port
python pygallery.py D:\Photos --bind 127.0.0.1 --port 8080

python pygallery.py D:\Photos --title "My Photos"
python pygallery.py D:\Photos -o D:\Photos\gallery -j 8
python pygallery.py D:\Photos --no-thumbs
```

From another machine on the LAN, open the printed `LAN:` URL (e.g.
`http://10.0.1.70:18923/gallery.html`).

### Arguments

| Argument | Description |
|----------|-------------|
| `root` | Directory to scan (prompted if omitted) |
| `-o` / `--output` | Asset output dir (default: `<root>/gallery`) |
| `-j` / `--workers` | Parallel thumbnail workers (default: `6`) |
| `--no-thumbs` | Skip ffmpeg thumbnail generation |
| `--no-serve` | Write files only; do not start HTTP server |
| `--bind` | Bind address (default: `0.0.0.0`) |
| `--port` | Port (default: `18923`) |
| `--title` | Page title (default: `Media Gallery`) |

## Usage (Snapchat)

```powershell
python pygallery-snapchat.py
python pygallery-snapchat.py D:\Temp\Snapchat
python pygallery-snapchat.py --enrich
```

Snapchat mode uses export-provided thumbnails/overlays and does not run ffmpeg
or start a server.

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
- The built-in server supports HTTP `Range` (video seeking in Chromium)
- Binding `0.0.0.0` exposes the library on your LAN; use `--bind 127.0.0.1`
  for local-only access
- If the port is busy, stop the other process or pass `--port N`
