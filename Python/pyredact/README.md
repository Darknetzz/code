# pyredact

Redact sensitive fields from Scandinavian financial exports (CSV/TSV/TXT/JSON/XML/HTML/XLSX/PDF/images and OFX/QIF).

PDF redaction uses PyMuPDF annotations so matched text is removed from the content stream, not merely covered. Image files and scanned PDF pages are OCR'd (Tesseract tessdata via PyMuPDF) and matching pixels are blanked. If OCR is unavailable, scanned/image-only sources are skipped and never written to the output folder.

## Requirements

```sh
pip install -r requirements.txt
```

OCR of images and scanned PDFs needs **Tesseract language data** (`tessdata`), not a separate Python OCR package. PyMuPDF already embeds the Tesseract engine.

- Windows: install [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) (includes `tessdata`), or pass `--tessdata` to that folder
- Or set `TESSDATA_PREFIX` to the `tessdata` directory
- Norwegian packs: install `nor` (optional). `--ocr-lang` defaults to `eng+nor` and drops codes that are not present

## Build the exe

Build from a **clean venv** (not the global Python). A global PyInstaller run will pack unrelated site-packages and balloon the binary:

```powershell
.\build.ps1
```

The exe does not bundle `tessdata`. Install Tesseract on the machine that runs it, or pass `--tessdata`.

## Usage

```sh
python pyredact.py --help
python pyredact.py
python pyredact.py -i ./exports -o ./redacted
python pyredact.py -i ./exports -r --dry-run
python pyredact.py -i statement.pdf --dry-run
python pyredact.py -i scan.png --tessdata "C:\Program Files\Tesseract-OCR\tessdata"
python pyredact.py -i ./exports --no-ocr
```

Missing `--input` / `--output` are prompted (input defaults to the current directory). Subdirectories trigger a recursive prompt unless `-r` / `--no-recursive` is set.

### Pattern templates

Default finance templates: `id` (fødselsnummer), `acct` (kontonr), `kid`, `num` (9+ digits).

Optional templates: `email`, `phone` (Nordic/international `+`), `url`.

```sh
python pyredact.py -i ./exports -t email -t phone -t url
python pyredact.py -i ./exports --replace-patterns -t email -p "\bIBAN[:\s]*[A-Z0-9]+=>[IBAN]"
```

- `--template` / `-t` — enable a named template (repeatable). Finance templates stay on unless `--replace-patterns`. Omitted: checkbox list (space to toggle, enter to confirm).
- `--pattern` / `-p` — extra `REGEX=>REPLACEMENT` (repeatable). Omitted: prompted until blank.
- `--replace-patterns` — do not auto-include the finance four.

## Common options

- `--input` / `-i` — file or directory
- `--output` / `-o` — output directory (default: `redacted` next to a file, or inside an input directory)
- `--encoding` / `-e` — text encoding (default: `utf-8-sig`; not used for PDF/XLSX/images)
- `--dry-run` / `-n` — list what would be written
- `--overwrite` / `-y` — overwrite existing outputs without asking
- `--recursive` / `-r` — include subdirectories (mirrors layout under output)
- `--ocr` / `--no-ocr` — OCR images and scanned PDF pages (default: on)
- `--tessdata` — Tesseract `tessdata` folder
- `--ocr-lang` — Tesseract languages, `+`-separated (default: `eng+nor`)

## Supported formats

- **CSV/TSV:** whitelist of date/description/amount columns; values scrubbed in-place
- **TXT/OFX/QFX/QIF:** whole-file scrub
- **JSON:** walk objects/arrays; scrub strings and sensitive integers
- **XML:** element text, tails, and attributes
- **HTML/HTM:** text nodes and attributes (BeautifulSoup)
- **XLSX:** all sheets/cells (openpyxl)
- **PDF:** text-layer redaction (PyMuPDF); image-only pages OCR'd when tessdata is available
- **PNG/JPEG/TIFF/BMP/GIF/WebP:** OCR, then blank matched pixels and write the same format

## Exit codes

- `0` — success
- `1` — no matching files, bad options, or missing dependency
- `2` — at least one file was not redacted
- `130` — interrupted
