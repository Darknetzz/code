# Create an isolated .venv for mafibot (avoids broken %AppData%\Roaming\Python user-site packages).
# Run from repo root:  .\setup-windows.ps1
#
# Playwright needs greenlet; on Windows + Python 3.14 the user-site wheel often fails with:
#   DLL load failed while importing _greenlet
# Prefer Python 3.12 from https://www.python.org/downloads/

param(
    [string]$VenvDir = ".venv",
    [switch]$SkipPlaywrightBrowsers
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Find-Python312 {
    $candidates = @(
        { & py -3.12 -c "import sys; print(sys.executable)" 2>$null },
        { & py -3.11 -c "import sys; print(sys.executable)" 2>$null },
        { & python3.12 -c "import sys; print(sys.executable)" 2>$null },
        { & python -c "import sys; print(sys.executable)" 2>$null }
    )
    foreach ($fn in $candidates) {
        try {
            $path = (& $fn).Trim()
            if ($path -and (Test-Path $path)) { return $path }
        } catch { }
    }
    return $null
}

function Test-GreenletImport {
    param([string]$PythonExe)
    & $PythonExe -c "import greenlet; from playwright.async_api import Page; print('ok')" 2>&1 | Out-Null
    return $LASTEXITCODE -eq 0
}

Write-Host "==> mafibot Windows setup" -ForegroundColor Cyan

$basePython = Find-Python312
if (-not $basePython) {
    Write-Host "No Python found. Install Python 3.12 and re-run." -ForegroundColor Red
    exit 1
}

$ver = & $basePython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "Using base interpreter: $basePython ($ver)" -ForegroundColor DarkGray

if ($ver -eq "3.14") {
    Write-Host @"

WARNING: Python 3.14 is not recommended for Playwright/greenlet on Windows.
Install Python 3.12 (python.org), then either:
  py -3.12 -m venv .venv
or re-run this script after 'py' launcher sees 3.12.

Continuing anyway; import test may fail.
"@ -ForegroundColor Yellow
}

$venvPython = Join-Path (Join-Path (Join-Path $Root $VenvDir) "Scripts") "python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "==> Creating venv: $VenvDir" -ForegroundColor Cyan
    & $basePython -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Invoke-Venv {
    param([Parameter(Mandatory)][string[]]$Args)
    & $venvPython @Args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "==> Upgrading pip" -ForegroundColor Cyan
Invoke-Venv -Args @("-m", "pip", "install", "--upgrade", "pip")

Write-Host "==> Installing MSVC runtime helper (Windows greenlet DLLs)" -ForegroundColor Cyan
Invoke-Venv -Args @("-m", "pip", "install", "msvc-runtime")

Write-Host "==> Installing mafibot dependencies" -ForegroundColor Cyan
Invoke-Venv -Args @("-m", "pip", "install", "-r", "requirements.txt")
$webbot = Join-Path (Join-Path $Root "..") "webbot"
if (Test-Path $webbot) {
    Invoke-Venv -Args @("-m", "pip", "install", "-e", $webbot)
}
Invoke-Venv -Args @("-m", "pip", "install", "-e", $Root)

if (-not $SkipPlaywrightBrowsers) {
    Write-Host "==> Installing Playwright Chromium" -ForegroundColor Cyan
    Invoke-Venv -Args @("-m", "playwright", "install", "chromium")
}

Write-Host "==> Verifying playwright import" -ForegroundColor Cyan
if (-not (Test-GreenletImport -PythonExe $venvPython)) {
    Write-Host @"

FAILED: greenlet/playwright still cannot load in the venv.

1. Install Python 3.12 from https://www.python.org/downloads/
2. Delete this folder and re-run:
     Remove-Item -Recurse -Force .venv
     py -3.12 .\setup-windows.ps1

3. Optional: remove broken user-site packages (only affects global python):
     python -m pip uninstall -y greenlet playwright

Always run mafibot with the venv:
     .\.venv\Scripts\Activate.ps1
     python .\mafibot.py --help
"@ -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host 'OK - use the venv for every command:' -ForegroundColor Green
Write-Host '  .\.venv\Scripts\Activate.ps1' -ForegroundColor White
Write-Host '  python .\mafibot.py ui' -ForegroundColor White
Write-Host ''
Write-Host 'Do NOT use bare python outside the venv; it still loads Roaming Python314 user packages.' -ForegroundColor DarkGray
