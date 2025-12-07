# pybin

Simple wrapper around PyInstaller to build a single-file executable from a Python script, with optional cleanup of build artifacts.

## Requirements
- Python 3.9+
- PyInstaller available on PATH (e.g., `pip install pyinstaller`)

## Usage
```bash
# Basic build (keeps .spec, cleans build/ afterward)
pybin my_script.py

# Build to a custom output directory
pybin my_script.py --output-dir D:/Apps/dist

# Remove the .spec file after build
pybin my_script.py --no-keep-spec

# Keep the build directory (for debugging or inspection)
pybin my_script.py --keep-build

# Keep both .spec and build/
pybin my_script.py --keep-spec --keep-build
```

## What it does
1. Validates the input file exists and ends with `.py`.
2. Runs `pyinstaller --onefile <script>` with paths anchored to the script's directory (not the CWD).
3. Optionally removes `build/` and the generated `.spec` unless you keep them via flags.
4. Leaves the resulting executable in the `dist/` folder next to the script by default.

## Flags
- `--keep-spec` — do not delete the generated `.spec` file after the build.
- `--keep-build` — do not delete the `build/` directory after the build.
- `--output-dir` — optional directory for the final executable; defaults to `<script_dir>/dist`.

## Notes
- The tool does not install PyInstaller for you; ensure it is installed and on PATH.
- The `.spec` file is regenerated each run unless you keep and reuse it with `--keep-spec`.
- By default the `dist/`, `build/`, and `.spec` live in the same directory as the input script (even if you run `pybin` from elsewhere).
- The final executable path defaults to `<script_dir>/dist/<script-name>.exe` on Windows.

## Shell Completion
To enable tab completion in PowerShell:

1. Generate the completion script:
   ```bash
   pybin --show-completion > ~\Documents\PowerShell\completions\pybin-completion.ps1
   ```

2. Add to your PowerShell profile (`$PROFILE`):
   ```powershell
   # Load all completion scripts
   Get-ChildItem "$HOME\Documents\PowerShell\completions\*.ps1" | ForEach-Object { . $_ }
   ```

3. Reload your profile:
   ```powershell
   . $PROFILE
   ```

**Note:** Avoid using `--install-completion` as it appends directly to your profile without formatting and can create duplicates. Use `--show-completion` and manually manage completion scripts instead.
