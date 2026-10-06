#!/usr/bin/env python3
"""
redact-finance.py

Redact sensitive information from Scandinavian financial CSV/PDF exports.

- CSV: keeps a whitelist of common columns; scrubs sensitive values in-place.
- PDF: uses PyMuPDF redaction annotations so matched text is removed from the
  content stream (not merely covered by black boxes).
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
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

console = Console()

SUPPORTED_SUFFIXES = {".csv", ".pdf"}

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


def _require_pymupdf():
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise SystemExit(
            "PyMuPDF is required for PDF redaction. Install with: pip install pymupdf"
        ) from exc
    return fitz


def count_pdf_matches(src: Path) -> tuple[int, int]:
    """Return (page_count, match_count) without writing."""
    fitz = _require_pymupdf()
    doc = fitz.open(src)
    try:
        matches = 0
        for page in doc:
            matches += len(iter_sensitive_matches(page.get_text()))
        return doc.page_count, matches
    finally:
        doc.close()


def redact_pdf(src: Path, dest: Path) -> tuple[int, int]:
    """
    Physically remove matched text via PyMuPDF redaction annotations.

    Returns (page_count, redaction_count).
    """
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
        return doc.page_count, redaction_count
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
                        pages, matches = count_pdf_matches(src)
                        detail = f"{pages}p / {matches} hits"
                    else:
                        detail = "—"
                    results.add_row(
                        kind,
                        src.name,
                        str(dest),
                        detail,
                        "[cyan]would write[/cyan]",
                    )
                elif src.suffix.lower() == ".csv":
                    rows, cols = redact_csv(src, dest, args.encoding)
                    results.add_row(
                        kind,
                        src.name,
                        str(dest),
                        f"{rows} rows / {cols} cols",
                        "[green]ok[/green]",
                    )
                else:
                    pages, redactions = redact_pdf(src, dest)
                    results.add_row(
                        kind,
                        src.name,
                        str(dest),
                        f"{pages}p / {redactions} redacted",
                        "[green]ok[/green]",
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
    if args.dry_run:
        console.print("[dim]Dry-run complete — no files written.[/dim]")
    else:
        console.print(f"[green]Done.[/green] Wrote to {output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
