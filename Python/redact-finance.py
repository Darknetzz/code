#!/usr/bin/env python3
"""
redact-finance.py

Redact sensitive information from Scandinavian financial CSV exports.

- Keeps only a whitelist of common columns (date, description, amount, in, out, etc).
- Redacts Norwegian personal numbers, account numbers, payment references, and any 9+ digit number.
- Accepts a single CSV file or a directory of CSVs.

Requires: pip install rich

Usage:
    python redact-finance.py
    python redact-finance.py -i ./exports -o ./redacted
    python redact-finance.py -i statement.csv --dry-run
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


def default_output_dir(input_path: Path) -> Path:
    """Place a 'redacted' folder next to the input file or directory."""
    return input_path.parent / "redacted"


def resolve_input_path(raw: str | None) -> Path:
    while True:
        value = raw or Prompt.ask("[bold]Input[/bold] CSV file or directory")
        path = Path(value).expanduser().resolve()
        if path.is_file() and path.suffix.lower() == ".csv":
            return path
        if path.is_dir():
            return path
        console.print(
            f"[red]Not a CSV file or directory:[/red] {path}",
        )
        raw = None


def resolve_output_dir(raw: str | None, input_path: Path) -> Path:
    default = default_output_dir(input_path)
    value = raw or Prompt.ask(
        "[bold]Output[/bold] directory",
        default=str(default),
    )
    return Path(value).expanduser().resolve()


def collect_csv_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(p for p in input_path.glob("*.csv") if p.is_file())


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description="Redact sensitive fields from Scandinavian financial CSV exports.",
    )
    parser.add_argument(
        "-i",
        "--input",
        help="CSV file or directory containing CSV files",
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
    files = collect_csv_files(input_path)

    if not files:
        console.print(f"[yellow]No CSV files found in[/yellow] {input_path}")
        return 1

    console.print(
        Panel.fit(
            f"[bold]Input[/bold]  {input_path}\n"
            f"[bold]Output[/bold] {output_dir}\n"
            f"[bold]Files[/bold]  {len(files)} CSV"
            + ("  [dim](dry-run)[/dim]" if args.dry_run else ""),
            title="redact-finance",
            border_style="cyan",
        )
    )

    results = Table(show_header=True, header_style="bold")
    results.add_column("Source")
    results.add_column("Destination")
    results.add_column("Rows", justify="right")
    results.add_column("Cols", justify="right")
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
            try:
                if args.dry_run:
                    results.add_row(
                        str(src.name),
                        str(dest),
                        "—",
                        "—",
                        "[cyan]would write[/cyan]",
                    )
                else:
                    rows, cols = redact_csv(src, dest, args.encoding)
                    results.add_row(
                        str(src.name),
                        str(dest),
                        str(rows),
                        str(cols),
                        "[green]ok[/green]",
                    )
            except Exception as exc:  # noqa: BLE001 - surface per-file errors
                results.add_row(
                    str(src.name),
                    str(dest),
                    "—",
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
