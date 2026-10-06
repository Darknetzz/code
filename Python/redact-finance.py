#!/usr/bin/env python3
"""
redact-finance.py

Redact sensitive information from Scandinavian financial exports.

- CSV/TSV: keeps a whitelist of common columns; scrubs sensitive values in-place.
- TXT/OFX/QFX/QIF: scrubs the whole file in-place (plain-text bank dumps).
- PDF: uses PyMuPDF redaction annotations so matched text is removed from the
  content stream (not merely covered by black boxes).
- Scanned/image-only PDFs (no text layer) are skipped and flagged as
  NOT REDACTED — they are never written to the output folder.
- Redacts Norwegian personal numbers, account numbers, payment references, and
  any 9+ digit number.

Requires:
    pip install rich pymupdf typer

Usage:
    python redact-finance.py --help
    python redact-finance.py
    python redact-finance.py -i ./exports -o ./redacted
    python redact-finance.py -i statement.pdf --dry-run
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

app = typer.Typer(
    add_completion=False,
    rich_markup_mode="rich",
    help=(
        "Redact sensitive fields from Scandinavian financial CSV/TSV/TXT/PDF "
        "(and OFX/QIF) exports.\n\n"
        "Missing [bold]--input[/bold] / [bold]--output[/bold] are prompted interactively."
    ),
)

console = Console()

CSV_SUFFIXES = {".csv", ".tsv"}
TEXT_SUFFIXES = {".txt", ".ofx", ".qfx", ".qif"}
PDF_SUFFIXES = {".pdf"}
SUPPORTED_SUFFIXES = CSV_SUFFIXES | TEXT_SUFFIXES | PDF_SUFFIXES
_FILE_COUNT_ORDER = ("CSV", "TSV", "TXT", "OFX", "QFX", "QIF", "PDF")
_FILE_COUNT_STYLE = {
    "CSV": "cyan",
    "TSV": "cyan",
    "TXT": "green",
    "OFX": "green",
    "QFX": "green",
    "QIF": "green",
    "PDF": "magenta",
}
# Pages with fewer alphanumeric chars than this are treated as having no usable text layer.
MIN_PAGE_ALNUM = 20

KEEP = {
    "dato",
    "date",
    "tekst",
    "beskrivelse",
    "description",
    "beløp",
    "belop",
    "amount",
    "inn",
    "ut",
}
PATTERNS = [
    (re.compile(r"\b\d{6}\s?\d{5}\b"), "[ID]"),  # fnr
    (re.compile(r"\b\d{4}[. ]?\d{2}[. ]?\d{5}\b"), "[ACCT]"),  # kontonr
    (re.compile(r"\bKID[:\s]*\d+", re.I), "KID"),
    (re.compile(r"\b\d{9,}\b"), "[NUM]"),  # any other long number
]


def scrub(value: str) -> tuple[str, int]:
    """Replace sensitive values. Returns (scrubbed_text, replacement_count)."""
    total = 0
    for pattern, replacement in PATTERNS:
        value, n = pattern.subn(replacement, value)
        total += n
    return value, total


def iter_sensitive_matches(text: str) -> list[tuple[str, str]]:
    """Return (matched_text, replacement) pairs found in text."""
    found: list[tuple[str, str]] = []
    for pattern, replacement in PATTERNS:
        for match in pattern.finditer(text):
            found.append((match.group(0), replacement))
    return found


def count_sensitive_replacements(text: str) -> int:
    """Count replacements scrub() would make (same sequential rules)."""
    return scrub(text)[1]


def default_output_dir(input_path: Path) -> Path:
    """Place a 'redacted' folder next to the input file or directory."""
    return input_path.parent / "redacted"


def resolve_input_path(raw: str | None) -> Path:
    while True:
        value = raw or Prompt.ask("[bold]Input[/bold] file or directory")
        path = Path(value).expanduser().resolve()
        if not path.exists():
            console.print(f"[red]Path does not exist:[/red] {path}")
        elif path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            return path
        elif path.is_dir():
            return path
        else:
            kinds = ", ".join(sorted(s.lstrip(".").upper() for s in SUPPORTED_SUFFIXES))
            console.print(
                f"[red]Not a supported file ({kinds}) or directory:[/red] {path}",
            )
        raw = None


def resolve_output_dir(raw: str | None, input_path: Path) -> Path:
    default = default_output_dir(input_path)
    value = raw or Prompt.ask(
        "[bold]Output[/bold] directory",
        default=str(default),
    )
    return Path(value).expanduser().resolve()


def collect_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    files = [
        p
        for p in input_path.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return sorted(files, key=lambda p: (p.suffix.lower(), p.name.lower()))


def confirm_write(dest: Path, *, overwrite: bool) -> bool:
    """Return True if dest may be written. Existing files require confirmation."""
    if not dest.exists() or overwrite:
        return True
    return Confirm.ask(
        f"[yellow]Overwrite existing file?[/yellow] {dest}",
        default=False,
    )


def read_csv_rows(src: Path, encoding: str) -> tuple[list[dict[str, str]], list[str]]:
    """Return (rows, kept_columns)."""
    with src.open(newline="", encoding=encoding) as fin:
        sample = fin.read(2048)
        fin.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        rows = list(csv.DictReader(fin, dialect=dialect))
    if not rows:
        return [], []
    cols = [c for c in rows[0] if c.strip().lower() in KEEP]
    return rows, cols


def count_csv_redactions(src: Path, encoding: str) -> tuple[int, int, int]:
    """Return (row_count, column_count, redaction_count) without writing."""
    rows, cols = read_csv_rows(src, encoding)
    if not rows:
        return 0, 0, 0
    redactions = 0
    for row in rows:
        for col in cols:
            redactions += count_sensitive_replacements(row[col])
    return len(rows), len(cols), redactions


def redact_csv(src: Path, dest: Path, encoding: str) -> tuple[int, int, int]:
    """Write a redacted CSV. Returns (row_count, column_count, redaction_count)."""
    rows, cols = read_csv_rows(src, encoding)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        dest.write_text("", encoding=encoding)
        return 0, 0, 0

    redactions = 0
    with dest.open("w", newline="", encoding=encoding) as fout:
        writer = csv.writer(fout)
        writer.writerow(cols)
        for row in rows:
            out_row = []
            for col in cols:
                scrubbed, n = scrub(row[col])
                redactions += n
                out_row.append(scrubbed)
            writer.writerow(out_row)
    return len(rows), len(cols), redactions


def line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def count_text_redactions(src: Path, encoding: str) -> tuple[int, int]:
    """Return (line_count, redaction_count) without writing."""
    text = src.read_text(encoding=encoding)
    return line_count(text), count_sensitive_replacements(text)


def redact_text(src: Path, dest: Path, encoding: str) -> tuple[int, int]:
    """Write a redacted text file. Returns (line_count, redaction_count)."""
    text = src.read_text(encoding=encoding)
    scrubbed, redactions = scrub(text)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(scrubbed, encoding=encoding)
    return line_count(text), redactions


class UnredactablePdfError(Exception):
    """PDF has no usable text layer; content cannot be safely redacted."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class PdfTextReport:
    page_count: int
    usable_pages: int
    empty_text_pages: list[int]  # 1-based page numbers
    match_count: int
    image_pages: int

    @property
    def has_usable_text(self) -> bool:
        return self.usable_pages > 0

    @property
    def is_likely_scanned(self) -> bool:
        return not self.has_usable_text and self.image_pages > 0


def _require_pymupdf():
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise SystemExit(
            "PyMuPDF is required for PDF redaction. Install with: pip install pymupdf"
        ) from exc
    return fitz


def _page_alnum_count(text: str) -> int:
    return sum(1 for c in text if c.isalnum())


def analyze_pdf(src: Path) -> PdfTextReport:
    """Inspect extractable text / images without modifying the file."""
    fitz = _require_pymupdf()
    doc = fitz.open(src)
    try:
        empty_text_pages: list[int] = []
        usable_pages = 0
        match_count = 0
        image_pages = 0
        for index, page in enumerate(doc, start=1):
            text = page.get_text()
            match_count += len(iter_sensitive_matches(text))
            if page.get_images(full=True):
                image_pages += 1
            if _page_alnum_count(text) >= MIN_PAGE_ALNUM:
                usable_pages += 1
            else:
                empty_text_pages.append(index)
        return PdfTextReport(
            page_count=doc.page_count,
            usable_pages=usable_pages,
            empty_text_pages=empty_text_pages,
            match_count=match_count,
            image_pages=image_pages,
        )
    finally:
        doc.close()


def _unredactable_reason(report: PdfTextReport) -> str:
    if report.is_likely_scanned:
        return (
            "no extractable text layer (likely scanned/image-only) — "
            "sensitive data may still be visible in images"
        )
    return (
        "no extractable text layer — cannot locate or remove sensitive values"
    )


def redact_pdf(src: Path, dest: Path) -> tuple[int, int, list[int]]:
    """
    Physically remove matched text via PyMuPDF redaction annotations.

    Returns (page_count, redaction_count, empty_text_pages).
    Raises UnredactablePdfError when the PDF has no usable text layer.
    """
    report = analyze_pdf(src)
    if not report.has_usable_text:
        raise UnredactablePdfError(_unredactable_reason(report))

    fitz = _require_pymupdf()
    # Tighter glyph boxes reduce accidental removal of neighboring lines.
    fitz.TOOLS.set_small_glyph_heights(True)

    doc = fitz.open(src)
    redaction_count = 0
    try:
        for page in doc:
            hits = iter_sensitive_matches(page.get_text())
            # Deduplicate identical strings on the page; search_for finds all instances.
            seen: set[str] = set()
            for matched_text, replacement in hits:
                if matched_text in seen:
                    continue
                seen.add(matched_text)
                for rect in page.search_for(matched_text):
                    page.add_redact_annot(
                        rect,
                        text=replacement,
                        fill=(0, 0, 0),
                        text_color=(1, 1, 1),
                        align=fitz.TEXT_ALIGN_CENTER,
                        cross_out=False,
                    )
                    redaction_count += 1
            # Remove overlapping text from the content stream (not just cover it).
            page.apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_NONE,
                graphics=fitz.PDF_REDACT_LINE_ART_NONE,
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        # Strip Title/Author/Subject/etc. and XMP so they cannot leak identifiers.
        doc.set_metadata({})
        doc.del_xml_metadata()
        # garbage/deflate purge removed content so it is not extractable later.
        doc.save(dest, garbage=4, deflate=True, clean=True)
        return doc.page_count, redaction_count, report.empty_text_pages
    finally:
        doc.close()


@dataclass
class FileWork:
    detail: str
    redactions: int
    empty_pages: list[int] = field(default_factory=list)
    skip_reason: str | None = None


def format_file_counts(files: list[Path]) -> str:
    counts = Counter(p.suffix.lower().lstrip(".").upper() for p in files)
    parts: list[str] = []
    for label in _FILE_COUNT_ORDER:
        n = counts.pop(label, 0)
        if not n:
            continue
        style = _FILE_COUNT_STYLE.get(label, "white")
        parts.append(f"[{style}]{n} {label}[/{style}]")
    for label, n in sorted(counts.items()):
        parts.append(f"{n} {label}")
    return ", ".join(parts)


def process_source(
    src: Path,
    dest: Path,
    encoding: str,
    *,
    write: bool,
) -> FileWork:
    """Inspect or redact one file. Unredactable PDFs return skip_reason instead of raising."""
    suffix = src.suffix.lower()
    if suffix in PDF_SUFFIXES:
        if not write:
            report = analyze_pdf(src)
            work = FileWork(
                detail=f"{report.page_count}p",
                redactions=report.match_count,
                empty_pages=report.empty_text_pages,
            )
            if not report.has_usable_text:
                work.skip_reason = _unredactable_reason(report)
            return work
        try:
            pages, redactions, empty_pages = redact_pdf(src, dest)
        except UnredactablePdfError as exc:
            return FileWork(detail="—", redactions=0, skip_reason=exc.reason)
        return FileWork(
            detail=f"{pages}p",
            redactions=redactions,
            empty_pages=empty_pages,
        )
    if suffix in CSV_SUFFIXES:
        if write:
            rows, cols, redactions = redact_csv(src, dest, encoding)
        else:
            rows, cols, redactions = count_csv_redactions(src, encoding)
        return FileWork(
            detail=f"{rows} rows / {cols} cols",
            redactions=redactions,
        )
    if suffix in TEXT_SUFFIXES:
        if write:
            lines, redactions = redact_text(src, dest, encoding)
        else:
            lines, redactions = count_text_redactions(src, encoding)
        return FileWork(detail=f"{lines} lines", redactions=redactions)
    raise ValueError(f"Unsupported file type: {suffix}")


@app.command()
def main(
    input: Annotated[
        Optional[Path],
        typer.Option(
            "--input",
            "-i",
            help="Supported file or directory (CSV, TSV, TXT, OFX/QFX/QIF, PDF).",
            show_default=False,
        ),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Output directory (prompt default: redacted next to input).",
            show_default=False,
        ),
    ] = None,
    encoding: Annotated[
        str,
        typer.Option(
            "--encoding",
            "-e",
            help="Text encoding for CSV/TSV/TXT and other text formats.",
        ),
    ] = "utf-8-sig",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            help="List files that would be written without creating them.",
        ),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite",
            "-y",
            help="Overwrite existing output files without asking.",
        ),
    ] = False,
) -> None:
    """Redact sensitive fields from Scandinavian financial exports."""
    input_path = resolve_input_path(str(input) if input is not None else None)
    output_dir = resolve_output_dir(
        str(output) if output is not None else None,
        input_path,
    )
    files = collect_files(input_path)

    if not files:
        kinds = ", ".join(sorted(s.lstrip(".").upper() for s in SUPPORTED_SUFFIXES))
        console.print(f"[yellow]No {kinds} files found in[/yellow] {input_path}")
        raise typer.Exit(1)

    counts = format_file_counts(files)
    console.print(
        Panel.fit(
            f"[bold]Input[/bold]  {input_path}\n"
            f"[bold]Output[/bold] {output_dir}\n"
            f"[bold]Files[/bold]  {len(files)} ({counts})"
            + ("  [dim](dry-run)[/dim]" if dry_run else ""),
            title="redact-finance",
            border_style="cyan",
        )
    )

    results = Table(show_header=True, header_style="bold")
    results.add_column("Type")
    results.add_column("Source")
    results.add_column("Destination")
    results.add_column("Detail", justify="right")
    results.add_column("Redactions", justify="right")
    results.add_column("Status")

    not_redacted: list[tuple[str, str]] = []
    partial_warnings: list[tuple[str, list[int]]] = []
    wrote_any = False
    skipped_overwrite = 0
    total_redactions = 0
    files_with_redactions = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Redacting", total=len(files))
        for src in files:
            dest = output_dir / src.name
            kind = src.suffix.lower().lstrip(".").upper()
            try:
                if not dry_run and not confirm_write(dest, overwrite=overwrite):
                    skipped_overwrite += 1
                    results.add_row(
                        kind,
                        src.name,
                        str(dest),
                        "—",
                        "—",
                        "[yellow]skipped (exists)[/yellow]",
                    )
                    continue

                work = process_source(src, dest, encoding, write=not dry_run)
                if work.skip_reason:
                    not_redacted.append((src.name, work.skip_reason))
                    results.add_row(
                        kind,
                        src.name,
                        "—",
                        work.detail,
                        str(work.redactions),
                        "[bold red]NOT REDACTED[/bold red]",
                    )
                    continue

                if not dry_run:
                    wrote_any = True
                total_redactions += work.redactions
                if work.redactions:
                    files_with_redactions += 1

                exists_note = (
                    " [yellow](would overwrite)[/yellow]"
                    if dry_run and dest.exists()
                    else ""
                )
                status = (
                    f"[cyan]would write[/cyan]{exists_note}"
                    if dry_run
                    else "[green]ok[/green]"
                )
                if work.empty_pages:
                    partial_warnings.append((src.name, work.empty_pages))
                    status += " [yellow](partial text)[/yellow]"
                results.add_row(
                    kind,
                    src.name,
                    str(dest),
                    work.detail,
                    str(work.redactions),
                    status,
                )
            except SystemExit:
                raise
            except Exception as exc:  # noqa: BLE001 - surface per-file errors
                results.add_row(
                    kind,
                    src.name,
                    str(dest),
                    "—",
                    "—",
                    f"[red]error: {exc}[/red]",
                )
            finally:
                progress.advance(task)

    console.print(results)

    summary_bits = [
        f"[bold]{total_redactions}[/bold] redaction(s)",
        f"across [bold]{files_with_redactions}[/bold] file(s)",
    ]
    if skipped_overwrite:
        summary_bits.append(f"[yellow]{skipped_overwrite} skipped (exists)[/yellow]")
    console.print(
        Panel.fit(
            " · ".join(summary_bits),
            title="Summary",
            border_style="cyan",
        )
    )

    if partial_warnings:
        lines = "\n".join(
            f" • [bold]{name}[/bold] — no text on page(s) "
            f"{', '.join(str(p) for p in pages)}"
            for name, pages in partial_warnings
        )
        console.print(
            Panel(
                "[bold yellow]PARTIAL TEXT LAYER[/bold yellow]\n\n"
                "These PDFs were processed, but some pages have little/no extractable "
                "text. Anything only present as an image on those pages was "
                "[bold]not[/bold] redacted.\n\n"
                f"{lines}",
                title="Warning",
                border_style="yellow",
            )
        )

    if not_redacted:
        lines = "\n".join(
            f" • [bold]{name}[/bold] — {reason}" for name, reason in not_redacted
        )
        console.print(
            Panel(
                "[bold white on red] NOT REDACTED [/bold white on red]\n\n"
                "These PDFs were [bold]skipped[/bold] and [bold]not[/bold] written to "
                "the output folder. Treat the originals as still sensitive.\n\n"
                f"{lines}\n\n"
                "[dim]Tip: export a text-based PDF from your bank, or OCR first, "
                "then re-run.[/dim]",
                title="⚠ DO NOT SHARE AS REDACTED",
                border_style="red",
            )
        )

    if dry_run:
        console.print("[dim]Dry-run complete — no files written.[/dim]")
    elif wrote_any:
        console.print(f"[green]Done.[/green] Wrote to {output_dir}")
    elif not_redacted and not skipped_overwrite:
        console.print("[red]Nothing was written — no PDF could be safely redacted.[/red]")
    elif skipped_overwrite and not wrote_any:
        console.print("[yellow]Nothing was written — existing outputs were left untouched.[/yellow]")

    if not_redacted:
        raise typer.Exit(2)


if __name__ == "__main__":
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted — exiting.[/yellow]")
        raise SystemExit(130) from None
