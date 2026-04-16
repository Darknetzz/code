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

# Same default dist/ folder, but a different executable name (e.g. side-by-side with a running build)
pybin my_script.py --name my_script_next
# or: pybin my_script.py -n my_script_next

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
<table>
   <tr><th>Flag</th><th>Description</th></tr>
   <tr><td>--keep-spec / --no-keep-spec</td><td>Keep or delete the generated .spec file after the build (default: keep).</td></tr>
   <tr><td>--keep-build</td><td>Keep the build directory after the build (default: removed).</td></tr>
   <tr><td>--output-dir &lt;PATH&gt;</td><td>Optional output directory for the final executable (default: &lt;script_dir&gt;/dist).</td></tr>
   <tr><td>--name / -n &lt;NAME&gt;</td><td>Base name of the built executable (no <code>.exe</code>); default: script stem. Output path is still <code>&lt;dist&gt;/&lt;NAME&gt;.exe</code>. Passed to PyInstaller as <code>--name</code>. If you use a custom <code>.spec</code> with a fixed <code>EXE(name=...)</code>, you may need to match that or rely on PyInstaller overriding it.</td></tr>
</table>

## Notes
- The tool does not install PyInstaller for you; ensure it is installed and on PATH.
- The `.spec` file is regenerated each run unless you keep and reuse it with `--keep-spec`.
- By default the `dist/`, `build/`, and `.spec` live in the same directory as the input script (even if you run `pybin` from elsewhere).
- The final executable path defaults to `<script_dir>/dist/<script-name>.exe` on Windows.

## Shell Completion
To enable tab completion in PowerShell:

1. Create the completions directory:
   ```bash
   mkdir ~\Documents\PowerShell\completions
   ```

2. Generate the completion script:
   ```bash
   pybin --show-completion > ~\Documents\PowerShell\completions\pybin-completion.ps1
   ```

3. Add to your PowerShell profile (`$PROFILE`):
   ```powershell
   # Load all completion scripts
   Get-ChildItem "$HOME\Documents\PowerShell\completions\*.ps1" | ForEach-Object { . $_ }
   ```

4. Reload your profile:
   ```powershell
   . $PROFILE
   ```

**Note:** Avoid using `--install-completion` as it appends directly to your profile without formatting and can create duplicates. Use `--show-completion` and manually manage completion scripts instead.
