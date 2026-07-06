# pyconvert

> **Future Rust candidate (tier 2):** No Rust port yet. A rewrite would target PDF/image rasterization throughput; keep Python if you rely on PyMuPDF/Pillow parity.

Universal CLI tool for converting files (media primarily). Supports **PDF→PNG/JPG** and **image format conversion** with resize, quality control, and batch processing. Built with **Typer** and **Rich**.

## Features

- **PDF to image** — Convert PDF pages to PNG, JPG, WebP, BMP, or TIFF (via PyMuPDF)
- **Image conversion** — Convert between PNG, JPG, WebP, BMP, TIFF, GIF (via Pillow)
- **Resize** — Width, height, or max-dimension (preserve aspect ratio)
- **Quality control** — JPEG/WebP quality (1–100)
- **Batch processing** — Directories, globs, recursive mode

## Installation

```bash
pip install -r requirements.txt
```

Or install dependencies directly:

```bash
pip install typer rich PyMuPDF Pillow
```

## Quick Start

```bash
# PDF to PNG
pyconvert pdf document.pdf -o ./output

# Image format conversion
pyconvert img photo.png -f jpg -q 90

# Check supported formats and backends
pyconvert list-formats
```

## Commands

| Command        | Description                                |
|----------------|--------------------------------------------|
| `pdf`          | Convert PDF(s) to images (PNG, JPG, etc.)  |
| `img`          | Convert images to another format, resize   |
| `list-formats` | Show supported formats and backend status  |

---

## `pdf` — PDF to Image

Convert PDF files to images. Each page becomes a separate image file (e.g. `report_page1.png`, `report_page2.png`).

### Synopsis

```bash
pyconvert pdf PATHS [OPTIONS]
```

### Arguments & Options

| Option        | Short | Default | Description                                    |
|---------------|-------|---------|------------------------------------------------|
| `PATHS`       | —     | *(required)* | PDF file(s) or directory to convert        |
| `--out`       | `-o`  | `.`     | Output directory                              |
| `--format`    | `-f`  | `png`   | Output format: png, jpg, jpeg, webp, bmp, tiff |
| `--dpi`       | —     | `150`   | Resolution (DPI) for rendering                 |
| `--quality`   | `-q`  | `85`    | JPEG/WebP quality (1–100)                      |
| `--first`     | —     | —       | First page (1-based)                           |
| `--last`      | —     | —       | Last page (1-based)                            |
| `--recursive` | `-r`  | `false` | Recurse into subdirectories                    |
| `--overwrite` | —     | `false` | Overwrite existing output files                |
| `--verbose`   | `-v`  | `false` | Show per-file progress                         |

### Examples

#### 1. Single PDF to PNG

```bash
pyconvert pdf document.pdf -o ./output
```

Produces `./output/document_page1.png`, `document_page2.png`, etc.

---

#### 2. PDF to JPG with higher quality

```bash
pyconvert pdf report.pdf -f jpg -q 90 -o ./images
```

Outputs JPG files with 90% quality.

---

#### 3. Higher DPI for print-quality output

```bash
pyconvert pdf report.pdf --dpi 300 -o ./high-res
```

Renders at 300 DPI instead of the default 150.

---

#### 4. Specific page range

```bash
pyconvert pdf report.pdf --first 1 --last 5 -o ./pages
```

Only converts pages 1 through 5.

---

#### 5. Batch convert directory

```bash
pyconvert pdf ./pdfs -o ./output
```

Converts all PDFs in `./pdfs` (non-recursive).

---

#### 6. Recursive batch

```bash
pyconvert pdf ./pdfs -f jpg -q 90 -r -o ./images
```

Recurses into subdirectories, converts to JPG at 90% quality.

---

#### 7. Globs and overwrite

```bash
pyconvert pdf *.pdf -o ./images --overwrite
```

Converts all PDFs in the current directory and overwrites existing output.

---

## `img` — Image Conversion & Resize

Convert images to another format and optionally resize. Handles EXIF orientation automatically.

### Synopsis

```bash
pyconvert img PATHS [OPTIONS]
```

### Arguments & Options

| Option           | Short | Default | Description                                      |
|------------------|-------|---------|--------------------------------------------------|
| `PATHS`          | —     | *(required)* | Image file(s) or directory to convert        |
| `--out`          | `-o`  | `.`     | Output directory                                |
| `--format`       | `-f`  | `png`   | Output format: png, jpg, webp, bmp, tiff         |
| `--quality`      | `-q`  | `85`    | JPEG/WebP quality (1–100)                        |
| `--width`        | `-W`  | —       | Output width (resize, preserve aspect)           |
| `--height`       | `-H`  | —       | Output height (resize, preserve aspect)          |
| `--max-dimension`| `-M`  | —       | Max width or height (preserve aspect)            |
| `--recursive`    | `-r`  | `false` | Recurse into subdirectories                      |
| `--overwrite`    | —     | `false` | Overwrite existing output files                  |
| `--verbose`      | `-v`  | `false` | Show per-file progress                           |
| `--extensions`   | `-e`  | `png,jpg,...` | Input extensions when scanning dirs      |

### Examples

#### 1. Single image format conversion

```bash
pyconvert img photo.png -f jpg -q 90
```

Converts `photo.png` to `photo.jpg` at 90% quality in the current directory.

---

#### 2. Resize by width (preserve aspect ratio)

```bash
pyconvert img photo.png --width 800 -o ./resized
```

Output width 800 px; height scales proportionally.

---

#### 3. Max dimension (thumbnail/preview)

```bash
pyconvert img ./photos -f webp --max-dimension 1920 -r -o ./web
```

Recurses `./photos`, converts to WebP, scales down so no side exceeds 1920 px.

---

#### 4. Batch convert PNGs to JPG

```bash
pyconvert img *.png -o ./output -f jpg -q 85
```

---

#### 5. Custom input extensions

```bash
pyconvert img ./raw -e "png,tiff,bmp" -f jpg -o ./jpg
```

Only processes PNG, TIFF, and BMP when scanning the directory.

---

#### 6. Resize by height

```bash
pyconvert img banner.png --height 400 -o ./thumbnails
```

---

#### 7. Width and height (exact dimensions)

```bash
pyconvert img logo.png --width 200 --height 200 -o ./icons
```

Resizes to exactly 200×200 (may distort aspect ratio).

---

## `list-formats` — Check Backends

Shows which conversion backends are installed and what formats they support.

```bash
pyconvert list-formats
```

Example output:

```
┌──────────┬────────┬─────────────────────────────────────┐
│ Backend  │ Status │ Formats                             │
├──────────┼────────┼─────────────────────────────────────┤
│ PyMuPDF  │   ✓    │ PDF → PNG, JPG, WebP, BMP, TIFF     │
│ Pillow   │   ✓    │ PNG, JPG, WebP, BMP, TIFF, GIF ↔ …  │
└──────────┴────────┴─────────────────────────────────────┘
```

---

## Summary

- **PDF** → use `pdf` with `--format`, `--dpi`, `--quality`, `--first`/`--last`
- **Images** → use `img` with `--format`, `--quality`, `--width`/`--height`/`--max-dimension`
- Use `-r` for recursive directory processing
- Use `--verbose` for per-file progress
- Use `list-formats` to verify backends
