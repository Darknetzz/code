# pybin

Simple wrapper around PyInstaller to build a single-file executable from a Python script, with optional cleanup of build artifacts.

## Requirements

- Python 3.9+
- Dependencies: `pip install -r requirements.txt` (Typer + PyInstaller), or ensure both are on PATH

## Bootstrap (first time in this monorepo)

Other Python projects are built via `pybin.exe` from [`!scripts/build-python.ps1`](../../!scripts/build-python.ps1). Build pybin once, then add `Python/pybin/dist` to PATH (or install the exe globally):

```powershell
cd Python/pybin
pip install -r requirements.txt
python -m PyInstaller --onefile pybin.py --distpath dist
# or: pyinstaller --onefile pybin.py
```

After that, `build-python.ps1` can compile sibling projects.

## Usage

```bash
# Basic build (default: direct --onefile, keeps .spec, cleans build/)
pybin my_script.py

# Use checked-in or generated .spec workflow (regenerates incompatible specs)
pybin my_script.py --use-spec

# Always build from .py without reading .spec
pybin my_script.py --no-use-spec

# Build multiple files at once
pybin a.py b.py c.py

# Build via a glob (quote so pybin expands it if the shell does not)
pybin "src/*.py"

# Skip helper modules when building >1 file (override with --include-underscore)
pybin src/*.py --include-underscore

# Exclude by fnmatch pattern
pybin src/*.py -x "*test*"

# Custom output directory / executable name (single file only for --name)
pybin my_script.py --output-dir D:/Apps/dist
pybin my_script.py --name my_app_next

# Artifact cleanup
pybin my_script.py --no-keep-spec
pybin my_script.py --keep-build
```

## What it does

1. Expands glob patterns, de-duplicates, filters underscore-prefixed helpers (multi-file) and `--exclude` matches.
2. Validates each input exists and is `.py`.
3. **Default:** runs `pyinstaller --onefile` from the script directory (`--no-use-spec` is default).
4. **With `--use-spec`:** uses `script.spec` if portable; otherwise runs `pyi-makespec`, patches the entry to a relative basename, then `pyinstaller script.spec`.
5. Optionally removes `build/` and `.spec` per flags.
6. Multi-file builds print a summary and exit non-zero if any file failed.

## Flags

| Flag | Description |
|------|-------------|
| `--use-spec` / `--no-use-spec` | Spec workflow vs direct onefile build (default: **no-use-spec**) |
| `--exclude` / `-x` | fnmatch skip pattern (repeatable) |
| `--include-underscore` | Include `_*.py` when building multiple files |
| `--keep-spec` / `--no-keep-spec` | Keep generated `.spec` (default: keep) |
| `--keep-build` | Keep `build/` directory |
| `--output-dir` | Output folder (default: `<script_dir>/dist`) |
| `--name` / `-n` | Executable stem (single file only) |

## Portable `.spec` files

Checked-in `.spec` files should use a **relative** entry, e.g. `['my_script.py']`, not machine-specific absolute paths. Incompatible specs are auto-regenerated when using `--use-spec`.

## Shell completion

Typer shell completion is **disabled** in this build (`add_completion=False`) to keep the PyInstaller bundle small. Use Typer’s documented install/show-completion flow from a dev install if you need completions:

```powershell
pip install -e .
pybin --install-completion powershell
```

For a one-file exe, prefer documenting flags in README rather than embedding completion scripts.

## Tests

```powershell
cd Python
python -m pytest pybin/tests -q
```
