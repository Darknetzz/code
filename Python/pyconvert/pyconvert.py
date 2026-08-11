"""
Universal CLI tool for converting files (media primarily).
Supports PDF→PNG/JPG, image format conversion, resize, and more.
Uses Typer + Rich for a highly customizable experience.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

# ---------------------------------------------------------------------------
# Optional backends (graceful fallback)
# ---------------------------------------------------------------------------

_pymupdf_available = False
_pillow_available = False

try:
    import fitz  # type: ignore[import-untyped]  # PyMuPDF

    _pymupdf_available = True
except ImportError:
    pass

try:
    from PIL import Image

    _pillow_available = True
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Defaults and constants
# ---------------------------------------------------------------------------

DEFAULT_DPI = 150
DEFAULT_JPEG_QUALITY = 85
SUPPORTED_IMAGE_FORMATS = ("png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif")
PDF_EXTENSIONS = (".pdf",)


# ---------------------------------------------------------------------------
# PDF → Image (PyMuPDF)
# ---------------------------------------------------------------------------


def _collect_pdf_paths(
    paths: list[Path], recursive: bool
) -> list[Path]:
    """Expand paths to concrete PDF files (handles directories)."""
    result: list[Path] = []
    for p in paths:
        if not p.exists():
            continue
        if p.is_file() and p.suffix.lower() == ".pdf":
            result.append(p.resolve())
        elif p.is_dir():
            if recursive:
                result.extend(
                    f for f in p.rglob("*.pdf") if f.is_file()
                )
            else:
                result.extend(
                    f for f in p.glob("*.pdf") if f.is_file()
                )
    return sorted(set(result))


def _convert_pdf_to_images(
    pdf_path: Path,
    out_dir: Path,
    fmt: str,
    *,
    dpi: float = DEFAULT_DPI,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    first_page: int | None = None,
    last_page: int | None = None,
    overwrite: bool = False,
) -> tuple[int, int]:
    """Convert a PDF to images. Returns (ok_count, fail_count)."""
    if not _pymupdf_available:
        raise RuntimeError("PyMuPDF is required for PDF conversion. Install with: pip install PyMuPDF")

    fmt_lower = fmt.lower().lstrip(".")
    if fmt_lower == "jpg":
        fmt_lower = "jpeg"

    doc = fitz.open(pdf_path)
    try:
        first = (first_page or 1) - 1  # 0-based
        last = (last_page or doc.page_count) - 1
        first = max(0, first)
        last = min(doc.page_count - 1, last)

        ok, fail = 0, 0
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        for i in range(first, last + 1):
            page = doc[i]
            out_name = f"{pdf_path.stem}_page{i + 1}.{fmt_lower}"
            out_path = out_dir / out_name

            if out_path.exists() and not overwrite:
                ok += 1
                continue

            try:
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pix.tobytes(fmt_lower if fmt_lower != "jpeg" else "jpeg", jpeg_quality)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "wb") as f:
                    f.write(img_bytes)
                ok += 1
            except Exception:
                fail += 1

        return (ok, fail)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Image → Image (Pillow)
# ---------------------------------------------------------------------------


def _collect_image_paths(
    paths: list[Path], recursive: bool, extensions: tuple[str, ...]
) -> list[Path]:
    """Expand paths to concrete image files."""
    result: list[Path] = []
    exts = {e.lower().lstrip(".") for e in extensions}
    for p in paths:
        if not p.exists():
            continue
        if p.is_file() and p.suffix.lower().lstrip(".") in exts:
            result.append(p.resolve())
        elif p.is_dir():
            if recursive:
                for f in p.rglob("*"):
                    if f.is_file() and f.suffix.lower().lstrip(".") in exts:
                        result.append(f.resolve())
            else:
                for f in p.glob("*"):
                    if f.is_file() and f.suffix.lower().lstrip(".") in exts:
                        result.append(f.resolve())
    return sorted(set(result))


def _convert_image(
    img_path: Path,
    out_path: Path,
    *,
    quality: int = DEFAULT_JPEG_QUALITY,
    width: int | None = None,
    height: int | None = None,
    max_dimension: int | None = None,
    overwrite: bool = False,
) -> bool:
    """Convert/resize a single image. Returns True on success."""
    if not _pillow_available:
        raise RuntimeError("Pillow is required for image conversion. Install with: pip install Pillow")

    if out_path.exists() and not overwrite:
        return True

    try:
        with Image.open(img_path) as im:
            # Handle orientation (EXIF)
            try:
                from PIL import ImageOps

                im = ImageOps.exif_transpose(im)
            except Exception:
                pass

            # Convert to RGB if saving to JPEG (no alpha)
            out_ext = out_path.suffix.lower().lstrip(".")
            if out_ext in ("jpg", "jpeg") and im.mode in ("RGBA", "P", "LA"):
                im = im.convert("RGB")

            # Resize
            w, h = im.size
            if width and height:
                im = im.resize((width, height), Image.Resampling.LANCZOS)
            elif width:
                ratio = width / w
                im = im.resize((width, int(h * ratio)), Image.Resampling.LANCZOS)
            elif height:
                ratio = height / h
                im = im.resize((int(w * ratio), height), Image.Resampling.LANCZOS)
            elif max_dimension and (w > max_dimension or h > max_dimension):
                if w >= h:
                    nw, nh = max_dimension, int(h * max_dimension / w)
                else:
                    nw, nh = int(w * max_dimension / h), max_dimension
                im = im.resize((nw, nh), Image.Resampling.LANCZOS)

            out_path.parent.mkdir(parents=True, exist_ok=True)

            save_kw: dict = {}
            if out_ext in ("jpg", "jpeg"):
                save_kw["quality"] = quality
                save_kw["optimize"] = True
            elif out_ext == "webp":
                save_kw["quality"] = quality

            im.save(out_path, **save_kw)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# CLI (Typer + Rich)
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="pyconvert",
    help="Universal CLI for converting files (PDF→image, image→image).",
    no_args_is_help=True,
)
console = Console()


def _make_progress() -> Progress | None:
    try:
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Command: pdf (PDF → PNG/JPG/…)
# ---------------------------------------------------------------------------

@app.command("pdf")
def pdf_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(..., help="PDF file(s) or directory to convert.", path_type=Path),
    ],
    out: Annotated[
        Path,
        typer.Option(".", "--out", "-o", path_type=Path, help="Output directory."),
    ] = Path("."),
    fmt: Annotated[
        str,
        typer.Option("png", "--format", "-f", help="Output format: png, jpg, jpeg, webp, bmp, tiff."),
    ] = "png",
    dpi: Annotated[
        float,
        typer.Option(DEFAULT_DPI, "--dpi", help="Resolution (DPI) for rendering."),
    ] = DEFAULT_DPI,
    quality: Annotated[
        int,
        typer.Option(DEFAULT_JPEG_QUALITY, "--quality", "-q", help="JPEG/WebP quality (1–100)."),
    ] = DEFAULT_JPEG_QUALITY,
    first: Annotated[
        int | None,
        typer.Option(None, "--first", help="First page (1-based)."),
    ] = None,
    last: Annotated[
        int | None,
        typer.Option(None, "--last", help="Last page (1-based)."),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option(False, "--recursive", "-r", help="Recurse into subdirectories."),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(False, "--overwrite", help="Overwrite existing output files."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(False, "--verbose", "-v", help="Show per-file progress."),
    ] = False,
):
    """
    Convert PDF(s) to images (PNG, JPG, etc.).

    Examples:

      pyconvert pdf document.pdf -o ./output

      pyconvert pdf ./pdfs -f jpg -q 90 --recursive

      pyconvert pdf report.pdf --first 1 --last 5 --dpi 200

      pyconvert pdf *.pdf -o ./images --overwrite
    """
    if not _pymupdf_available:
        console.print("[red]PyMuPDF is required. Install with: pip install PyMuPDF[/]")
        raise typer.Exit(1)

    pdf_files = _collect_pdf_paths(list(paths), recursive)
    if not pdf_files:
        console.print("[yellow]No PDF files found.[/]")
        raise typer.Exit(0)

    out_dir = out.resolve()
    total_ok, total_fail = 0, 0
    time_started = datetime.now()

    progress = _make_progress()
    if progress and verbose:
        with progress:
            task = progress.add_task("Converting PDFs...", total=len(pdf_files))
            for pdf_path in pdf_files:
                progress.update(task, description=pdf_path.name)
                ok, fail = _convert_pdf_to_images(
                    pdf_path,
                    out_dir,
                    fmt,
                    dpi=dpi,
                    jpeg_quality=quality,
                    first_page=first,
                    last_page=last,
                    overwrite=overwrite,
                )
                total_ok += ok
                total_fail += fail
                progress.advance(task)
    else:
        for pdf_path in pdf_files:
            if verbose:
                console.print(f"  [dim]{pdf_path.name}[/]")
            ok, fail = _convert_pdf_to_images(
                pdf_path,
                out_dir,
                fmt,
                dpi=dpi,
                jpeg_quality=quality,
                first_page=first,
                last_page=last,
                overwrite=overwrite,
            )
            total_ok += ok
            total_fail += fail

    time_completed = datetime.now()
    elapsed = time_completed - time_started
    elapsed_str = str(elapsed).split(".")[0] if elapsed.total_seconds() >= 1 else f"{elapsed.total_seconds():.2f}s"

    table = Table(title="PDF conversion")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_row("PDFs processed", str(len(pdf_files)))
    table.add_row("Pages converted", str(total_ok))
    table.add_row("Failed", str(total_fail))
    table.add_row("Time started", time_started.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("Time completed", time_completed.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("Time elapsed", elapsed_str)
    console.print(Panel(table, title="Done", border_style="green"))


# ---------------------------------------------------------------------------
# Command: img (Image → Image)
# ---------------------------------------------------------------------------


@app.command("img")
def img_cmd(
    paths: Annotated[
        list[Path],
        typer.Argument(..., help="Image file(s) or directory to convert.", path_type=Path),
    ],
    out: Annotated[
        Path,
        typer.Option(".", "--out", "-o", path_type=Path, help="Output directory."),
    ] = Path("."),
    img_format: Annotated[
        str,
        typer.Option("png", "--format", "-f", help="Output format: png, jpg, webp, bmp, tiff."),
    ] = "png",
    quality: Annotated[
        int,
        typer.Option(DEFAULT_JPEG_QUALITY, "--quality", "-q", help="JPEG/WebP quality (1–100)."),
    ] = DEFAULT_JPEG_QUALITY,
    width: Annotated[
        int | None,
        typer.Option(None, "--width", "-W", help="Output width (resize)."),
    ] = None,
    height: Annotated[
        int | None,
        typer.Option(None, "--height", "-H", help="Output height (resize)."),
    ] = None,
    max_dimension: Annotated[
        int | None,
        typer.Option(None, "--max-dimension", "-M", help="Max width or height (preserve aspect)."),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option(False, "--recursive", "-r", help="Recurse into subdirectories."),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(False, "--overwrite", help="Overwrite existing output files."),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(False, "--verbose", "-v", help="Show per-file progress."),
    ] = False,
    extensions: Annotated[
        str,
        typer.Option(
            "png,jpg,jpeg,webp,bmp,tiff,gif",
            "--extensions",
            "-e",
            help="Input extensions (comma-separated) when scanning dirs.",
        ),
    ] = "png,jpg,jpeg,webp,bmp,tiff,gif",
):
    """
    Convert images to another format and optionally resize.

    Examples:

      pyconvert img photo.png -f jpg -q 90

      pyconvert img ./photos -f webp --max-dimension 1920 -r

      pyconvert img *.png -o ./output --width 800

      pyconvert img ./raw -f jpg --quality 95 --overwrite
    """
    if not _pillow_available:
        console.print("[red]Pillow is required. Install with: pip install Pillow[/]")
        raise typer.Exit(1)

    ext_tuple = tuple("." + x.strip().lstrip(".") for x in extensions.split(",") if x.strip())
    if not ext_tuple:
        ext_tuple = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif")

    img_files = _collect_image_paths(list(paths), recursive, ext_tuple)
    if not img_files:
        console.print("[yellow]No image files found.[/]")
        raise typer.Exit(0)

    out_dir = out.resolve()
    fmt_ext = img_format.lower().lstrip(".")
    if fmt_ext == "jpg":
        fmt_ext = "jpeg"

    ok_count, fail_count = 0, 0
    time_started = datetime.now()

    progress = _make_progress()
    if progress and verbose:
        with progress:
            task = progress.add_task("Converting images...", total=len(img_files))
            for img_path in img_files:
                progress.update(task, description=img_path.name)
                out_name = f"{img_path.stem}.{fmt_ext}"
                out_path = out_dir / out_name
                if _convert_image(
                    img_path,
                    out_path,
                    quality=quality,
                    width=width,
                    height=height,
                    max_dimension=max_dimension,
                    overwrite=overwrite,
                ):
                    ok_count += 1
                else:
                    fail_count += 1
                progress.advance(task)
    else:
        for img_path in img_files:
            out_name = f"{img_path.stem}.{fmt_ext}"
            out_path = out_dir / out_name
            if _convert_image(
                img_path,
                out_path,
                quality=quality,
                width=width,
                height=height,
                max_dimension=max_dimension,
                overwrite=overwrite,
            ):
                ok_count += 1
            else:
                fail_count += 1

    time_completed = datetime.now()
    elapsed = time_completed - time_started
    elapsed_str = str(elapsed).split(".")[0] if elapsed.total_seconds() >= 1 else f"{elapsed.total_seconds():.2f}s"

    table = Table(title="Image conversion")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_row("Images processed", str(len(img_files)))
    table.add_row("Converted", str(ok_count))
    table.add_row("Failed", str(fail_count))
    table.add_row("Time started", time_started.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("Time completed", time_completed.strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("Time elapsed", elapsed_str)
    console.print(Panel(table, title="Done", border_style="green"))


# ---------------------------------------------------------------------------
# Command: list-formats (show supported formats)
# ---------------------------------------------------------------------------


@app.command("list-formats")
def list_formats():
    """List supported formats and conversion backends."""
    table = Table(title="Supported formats")
    table.add_column("Backend", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Formats", style="green")
    table.add_row(
        "PyMuPDF",
        "[green]✓[/]" if _pymupdf_available else "[red]✗[/]",
        "PDF → PNG, JPG, WebP, BMP, TIFF",
    )
    table.add_row(
        "Pillow",
        "[green]✓[/]" if _pillow_available else "[red]✗[/]",
        "PNG, JPG, WebP, BMP, TIFF, GIF ↔ …",
    )
    console.print(Panel(table, title="pyconvert", border_style="blue"))
    if not _pymupdf_available or not _pillow_available:
        console.print("\n[dim]Install missing: pip install PyMuPDF Pillow[/]")


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
