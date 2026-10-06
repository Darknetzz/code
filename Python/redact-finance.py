#!/usr/bin/env python3
"""
redact-finance.py

Redact sensitive information from Scandinavian financial CSV/PDF exports.

- CSV: keeps a whitelist of common columns; scrubs sensitive values in-place.
- PDF: uses PyMuPDF redaction annotations so matched text is removed from the
  content stream (not merely covered by black boxes).
- Scanned/image-only PDFs (no text layer) are skipped and flagged as
  NOT REDACTED — they are never written to the output folder.
- Redacts Norwegian personal numbers, account numbers, payment references, and
  any 9+ digit number.

Requires:
    pip install rich pymupdf

Usage:
    python redact-finance.py
    python redact-finance.py -i ./exports -o ./redacted
    python redact-finance.py -i statement.pdf --dry-run
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

console = Console()

SUPPORTED_SUFFIXES = {".csv", ".pdf"}
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


def scrub(value: str) -> str:
    for pattern, replacement in PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def iter_sensitive_matches(text: str) -> list[tuple[str, str]]:
    """Return (matched_text, replacement) pairs found in text."""
    found: list[tuple[str, str]] = []
    for pattern, replacement in PATTERNS:
        for match in pattern.finditer(text):
            found.append((match.group(0), replacement))
    return found


def default_output_dir(input_path: Path) -> Path:
    """Place a 'redacted' folder next to the input file or directory."""
    return input_path.parent / "redacted"


def resolve_input_path(raw: str | None) -> Path:
    while True:
        value = raw or Prompt.ask("[bold]Input[/bold] CSV/PDF file or directory")
        path = Path(value).expanduser().resolve()
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            return path
        if path.is_dir():
            return path
        console.print(
            f"[red]Not a CSV/PDF file or directory:[/red] {path}",
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


def redact_csv(src: Path, dest: Path, encoding: str) -> tuple[int, int]:
    """Write a redacted CSV. Returns (row_count, column_count)."""
    with src.open(newline="", encoding=encoding) as fin:
        sample = fin.read(2048)
        fin.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        rows = list(csv.DictReader(fin, dialect=dialect))

    if not rows:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("", encoding=encoding)
        return 0, 0

    cols = [c for c in rows[0] if c.strip().lower() in KEEP]
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", newline="", encoding=encoding) as fout:
        writer = csv.writer(fout)
        writer.writerow(cols)
        for row in rows:
            writer.writerow([scrub(row[c]) for c in cols])
    return len(rows), len(cols)


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
        # garbage/deflate purge removed content so it is not extractable later.
        doc.save(dest, garbage=4, deflate=True, clean=True)
        return doc.page_count, redaction_count, report.empty_text_pages
    finally:
        doc.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description="Redact sensitive fields from Scandinavian financial CSV/PDF exports.",
    )
    parser.add_argument(
        "-i",
        "--input",
        help="CSV/PDF file or directory containing such files",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output directory (default when prompted: redacted next to input)",
    )
    parser.add_argument(
        "-e",
        "--encoding",
        default="utf-8-sig",
        help="Text encoding for reading/writing CSVs (default: utf-8-sig)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="List files that would be written without creating them",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    input_path = resolve_input_path(args.input)
    output_dir = resolve_output_dir(args.output, input_path)
    files = collect_files(input_path)

    if not files:
        console.print(f"[yellow]No CSV/PDF files found in[/yellow] {input_path}")
        return 1

    csv_n = sum(1 for f in files if f.suffix.lower() == ".csv")
    pdf_n = sum(1 for f in files if f.suffix.lower() == ".pdf")
    console.print(
        Panel.fit(
            f"[bold]Input[/bold]  {input_path}\n"
            f"[bold]Output[/bold] {output_dir}\n"
            f"[bold]Files[/bold]  {len(files)} "
            f"([cyan]{csv_n} CSV[/cyan], [magenta]{pdf_n} PDF[/magenta])"
            + ("  [dim](dry-run)[/dim]" if args.dry_run else ""),
            title="redact-finance",
            border_style="cyan",
        )
    )

    results = Table(show_header=True, header_style="bold")
    results.add_column("Type")
    results.add_column("Source")
    results.add_column("Destination")
    results.add_column("Detail", justify="right")
    results.add_column("Status")

    not_redacted: list[tuple[str, str]] = []
    partial_warnings: list[tuple[str, list[int]]] = []
    wrote_any = False

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
                if args.dry_run:
                    if src.suffix.lower() == ".pdf":
                        report = analyze_pdf(src)
                        detail = f"{report.page_count}p / {report.match_count} hits"
                        if not report.has_usable_text:
                            reason = _unredactable_reason(report)
                            not_redacted.append((src.name, reason))
                            results.add_row(
                                kind,
                                src.name,
                                "—",
                                detail,
                                "[bold red]NOT REDACTED[/bold red]",
                            )
                        else:
                            status = "[cyan]would write[/cyan]"
                            if report.empty_text_pages:
                                partial_warnings.append(
                                    (src.name, report.empty_text_pages)
                                )
                                status = (
                                    "[cyan]would write[/cyan] "
                                    "[yellow](partial text)[/yellow]"
                                )
                            results.add_row(
                                kind, src.name, str(dest), detail, status
                            )
                    else:
                        results.add_row(
                            kind,
                            src.name,
                            str(dest),
                            "—",
                            "[cyan]would write[/cyan]",
                        )
                elif src.suffix.lower() == ".csv":
                    rows, cols = redact_csv(src, dest, args.encoding)
                    wrote_any = True
                    results.add_row(
                        kind,
                        src.name,
                        str(dest),
                        f"{rows} rows / {cols} cols",
                        "[green]ok[/green]",
                    )
                else:
                    pages, redactions, empty_pages = redact_pdf(src, dest)
                    wrote_any = True
                    status = "[green]ok[/green]"
                    if empty_pages:
                        partial_warnings.append((src.name, empty_pages))
                        status = "[green]ok[/green] [yellow](partial text)[/yellow]"
                    results.add_row(
                        kind,
                        src.name,
                        str(dest),
                        f"{pages}p / {redactions} redacted",
                        status,
                    )
            except UnredactablePdfError as exc:
                not_redacted.append((src.name, exc.reason))
                results.add_row(
                    kind,
                    src.name,
                    "—",
                    "—",
                    "[bold red]NOT REDACTED[/bold red]",
                )
            except SystemExit:
                raise
            except Exception as exc:  # noqa: BLE001 - surface per-file errors
                results.add_row(
                    kind,
                    src.name,
                    str(dest),
                    "—",
                    f"[red]error: {exc}[/red]",
                )
            progress.advance(task)

    console.print(results)

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

    if args.dry_run:
        console.print("[dim]Dry-run complete — no files written.[/dim]")
    elif wrote_any:
        console.print(f"[green]Done.[/green] Wrote to {output_dir}")
    elif not_redacted:
        console.print("[red]Nothing was written — no PDF could be safely redacted.[/red]")

    return 2 if not_redacted else 0


if __name__ == "__main__":
    sys.exit(main())
