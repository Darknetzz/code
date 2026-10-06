# pyredact

Redact sensitive fields from Scandinavian financial exports (CSV/TSV/TXT/JSON/XML/HTML/XLSX/PDF and OFX/QIF).

PDF redaction uses PyMuPDF annotations so matched text is removed from the content stream, not merely covered. Scanned/image-only PDFs are skipped and never written to the output folder.

## Requirements

```sh
pip install -r requirements.txt
```

## Usage

```sh
python pyredact.py --help
python pyredact.py
python pyredact.py -i ./exports -o ./redacted
python pyredact.py -i ./exports -r --dry-run
python pyredact.py -i statement.pdf --dry-run
```

Missing `--input` / `--output` are prompted (input defaults to the current directory). Subdirectories trigger a recursive prompt unless `-r` / `--no-recursive` is set.

### Pattern templates

Default finance templates: `id` (fødselsnummer), `acct` (kontonr), `kid`, `num` (9+ digits).

Optional templates: `email`, `phone` (Nordic/international `+`), `url`.

```sh
python pyredact.py -i ./exports -t email -t phone -t url
python pyredact.py -i ./exports --replace-patterns -t email -p "\bIBAN[:\s]*[A-Z0-9]+=>[IBAN]"
```

- `--template` / `-t` — enable a named template (repeatable). Finance templates stay on unless `--replace-patterns`. Omitted: interactive checklist (askr).
- `--pattern` / `-p` — extra `REGEX=>REPLACEMENT` (repeatable). Omitted: prompted until blank.
- `--replace-patterns` — do not auto-include the finance four.

## Common options

- `--input` / `-i` — file or directory
- `--output` / `-o` — output directory (default: `redacted` next to a file, or inside an input directory)
- `--encoding` / `-e` — text encoding (default: `utf-8-sig`; not used for PDF/XLSX)
- `--dry-run` / `-n` — list what would be written
- `--overwrite` / `-y` — overwrite existing outputs without asking
- `--recursive` / `-r` — include subdirectories (mirrors layout under output)

## Supported formats

- **CSV/TSV:** whitelist of date/description/amount columns; values scrubbed in-place
- **TXT/OFX/QFX/QIF:** whole-file scrub
- **JSON:** walk objects/arrays; scrub strings and sensitive integers
- **XML:** element text, tails, and attributes
- **HTML/HTM:** text nodes and attributes (BeautifulSoup)
- **XLSX:** all sheets/cells (openpyxl)
- **PDF:** text-layer redaction (PyMuPDF)

## Exit codes

- `0` — success
- `1` — no matching files, bad options, or missing dependency
- `2` — at least one PDF was not redacted
- `130` — interrupted
