# pyredact — Bulk PDF, CSV, XML, HTML, XLSX Redaction Tool

`pyredact` is a Python-based CLI utility for detecting and **permanently removing sensitive data** (names, account numbers, addresses, etc.) from downloadable PDFs and other financial/electronic documents. It is designed for use-cases like preparing redacted bank statements, invoices, or transaction exports for sharing or audits.

It **overwrites sensitive text**, not just overlays or draws boxes, making it safe for disclosure.

## Features

- Redacts PDFs **in-place**—removes matched values using MuPDF (PyMuPDF)
- Supports CSV, XML, HTML, XLSX in addition to PDF
- Customizable patterns for names, bank details, addresses, transaction IDs, etc.
- **Dry-run mode:** preview what will be redacted before writing changes
- Table output summarizes redactions, partials, errors
- Handles both single files and directories (with file type auto-detection)
- Skips files with no extractable text layer (and warns if likely scanned/image-only)
- Partial page warnings if some PDF pages have no text layer (image-only scans)
- Clear report and warnings for unredactable files

## Requirements

- Python 3.8+
- For PDFs: [`pymupdf`](https://github.com/pymupdf/PyMuPDF)
- For Excel: [`openpyxl`](https://openpyxl.readthedocs.io/en/stable/)
- For HTML: [`beautifulsoup4`](https://www.crummy.com/software/BeautifulSoup/)

Install all dependencies using:

```sh
pip install -r requirements.txt
```

## Usage

```sh
python pyredact.py [OPTIONS] [FILES or DIRECTORIES ...]
```

### Example commands

**Dry-run on a sample folder (see what would be redacted):**
```sh
python pyredact.py --dry-run input-folder/
```

**Redact all PDFs in a directory and save to output folder (`--output`):**
```sh
python pyredact.py --output redacted/ input-folder/
```

**Redact a single file, overwriting if allowed:**
```sh
python pyredact.py statement.pdf --overwrite
```

**Custom config/pattern set:**
```sh
python pyredact.py --config my_patterns.yaml --output safe/ docs/
```

### Common Options

- `--dry-run` — Don't write files; display what **would** change
- `--output DIR` — Where to write redacted files (default: output/ or alongside input)
- `--overwrite` — Overwrite existing output files without prompt
- `--config FILE` — YAML config of additional/custom patterns to redact
- `--no-pdf` — Skip PDF files
- `--no-txt` — Skip text/CSV/XML/HTML files

## Supported Formats

- **PDF:** Redacts actual text layer (uses PyMuPDF). Warns/skips scanned/image-only.
- **CSV/TXT:** Overwrites matched values in all cells/fields.
- **XML:** Redacts content in elements/attributes.
- **HTML:** Redacts all text nodes and string attributes (BeautifulSoup).
- **XLSX:** Redacts in-place (with openpyxl).

## Output

Upon completion, a summary table is displayed indicating:

- File name/type
- What was redacted and how many values were replaced
- Warnings for partially processed PDFs (no text layer)
- Errors/skips with reasons (e.g., can't redact images)

**Exit codes:**
- `0`: Success, all files processed/redacted
- `2`: Some files not redacted or skipped

## Caveats & Tips

- **Image/Scanned PDFs:** If your PDF is a scanned image, there is no extractable text layer. Use an OCR tool to convert to searchable PDF first (then re-run).
- **Redact before sharing:** Always review output and never rely on manual inspection alone.
- **Sensitive patterns:** Default config includes financial/accounting patterns; edit config for custom needs.

## Example YAML config for Custom Patterns

```yaml
patterns:
  - name: SSN
    regex: "\\b\\d{3}-\\d{2}-\\d{4}\\b"
    replacement: "***-**-****"
  - name: DriverLicense
    regex: "[A-Z]\\d{7}"
    replacement: "DL-REDACTED"
```

Then run with `--config my_patterns.yaml`.

## Troubleshooting

- **Module not found:** Install missing dependencies as prompted (e.g. `pymupdf`, `openpyxl`, or `beautifulsoup4`).
- **Scanned PDFs not redacted:** Use OCR tools (e.g. Adobe, Tesseract) to create a text layer.
- **See skipped or partially redacted files?** Review the summary for details and fix source files as needed.

## Development

- Core: `pyredact.py`
- See code for detailed logic/documentation.
- Tests and new pattern configs welcome via PR!

## License

MIT License. See [LICENSE](../../LICENSE).

---