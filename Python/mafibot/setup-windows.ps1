# Create an isolated .venv for mafibot (avoids broken %AppData%\Roaming\Python user-site packages).
# Run from repo root:  .\setup-windows.ps1
#
# Playwright needs greenlet. On Windows, Python 3.14 is unreliable — use 3.12.

param(
    [string]$VenvDir = ".venv",
    [string]$PythonExe = "",
    [switch]$SkipPlaywrightBrowsers,
    [switch]$AllowPython314
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Get-PythonVersion {
    param([string]$Exe)
    & $Exe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
}

function Find-BestPython {
    if ($PythonExe -and (Test-Path $PythonExe)) {
        return (Resolve-Path $PythonExe).Path
    }

    $candidates = [System.Collections.Generic.List[string]]::new()
    foreach ($launcher in @(
            { & py -3.12 -c "import sys; print(sys.executable)" 2>$null },
            { & py -3.11 -c "import sys; print(sys.executable)" 2>$null },
            { & python3.12 -c "import sys; print(sys.executable)" 2>$null }
        )) {
        try {
            $p = (& $launcher).Trim()
            if ($p) { $candidates.Add($p) }
        } catch { }
    }

    $searchDirs = @(
        "$env:LOCALAPPDATA\Programs\Python",
        "${env:ProgramFiles}\Python312",
        "${env:ProgramFiles(x86)}\Python312"
    )
    foreach ($dir in $searchDirs) {
        if (-not (Test-Path $dir)) { continue }
        Get-ChildItem -Path $dir -Recurse -Filter "python.exe" -ErrorAction SilentlyContinue |
            ForEach-Object { $candidates.Add($_.FullName) }
    }

    $seen = @{}
    foreach ($path in $candidates) {
        if (-not $path -or -not (Test-Path $path)) { continue }
        if ($seen[$path]) { continue }
        $seen[$path] = $true
        try {
            $ver = Get-PythonVersion -Exe $path
            if ($ver -eq "3.12" -or $ver -eq "3.11") { return $path }
        } catch { }
    }

    if ($AllowPython314) {
        try {
            $path = (& python -c "import sys; print(sys.executable)").Trim()
            if ($path -and (Test-Path $path)) { return $path }
        } catch { }
    }

    return $null
}

function Test-PlaywrightImport {
    param([string]$Exe)
    $code = @'
try:
    import msvc_runtime
except ImportError:
    pass
import greenlet
from playwright.async_api import Page
print("ok")
'@
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $out = & $Exe -s -c $code 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return @{ Ok = ($code -eq 0); Output = ($out -join "`n") }
}

Write-Host "==> mafibot Windows setup" -ForegroundColor Cyan

$basePython = Find-BestPython
if (-not $basePython) {
    Write-Host @"
No suitable Python found (need 3.11 or 3.12).

1. Download Python 3.12: https://www.python.org/downloads/release/python-31210/
   (check "Add python.exe to PATH" and "py launcher")
2. Re-run:  .\setup-windows.ps1
   Or:     .\setup-windows.ps1 -PythonExe "C:\Path\To\Python312\python.exe"

To force Python 3.14 (not recommended):  .\setup-windows.ps1 -AllowPython314
"@ -ForegroundColor Red
    exit 1
}

$ver = Get-PythonVersion -Exe $basePython
Write-Host "Using base interpreter: $basePython ($ver)" -ForegroundColor DarkGray

if ($ver -eq "3.14" -and -not $AllowPython314) {
    Write-Host "Refusing Python 3.14 (greenlet often fails). Install 3.12 or pass -AllowPython314." -ForegroundColor Red
    exit 1
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

Write-Host "==> Installing dependencies" -ForegroundColor Cyan
Invoke-Venv -Args @("-m", "pip", "install", "-r", "requirements.txt")

Write-Host "==> Reinstalling greenlet + playwright (no cache)" -ForegroundColor Cyan
Invoke-Venv -Args @("-m", "pip", "install", "--force-reinstall", "--no-cache-dir", "greenlet", "playwright")
Invoke-Venv -Args @("-m", "pip", "uninstall", "-y", "msvc-runtime") 2>$null | Out-Null

$webbot = Join-Path (Join-Path $Root "..") "webbot"
if (Test-Path $webbot) {
    Invoke-Venv -Args @("-m", "pip", "install", "-e", $webbot)
}
Invoke-Venv -Args @("-m", "pip", "install", "-e", $Root)

if (-not $SkipPlaywrightBrowsers) {
    Write-Host "==> Installing Playwright Chromium" -ForegroundColor Cyan
    Invoke-Venv -Args @("-m", "playwright", "install", "chromium")
}

Write-Host "==> Verifying playwright import (-s = no user-site)" -ForegroundColor Cyan
$check = Test-PlaywrightImport -Exe $venvPython
if (-not $check.Ok) {
    Write-Host "Import failed:" -ForegroundColor Red
    Write-Host $check.Output -ForegroundColor Red
    Write-Host @"

Next steps:
  Remove-Item -Recurse -Force .venv
  Install Python 3.12 from python.org
  .\setup-windows.ps1 -PythonExe "C:\Users\Kriss\AppData\Local\Programs\Python\Python312\python.exe"

Then always:
  .\.venv\Scripts\Activate.ps1
  python .\mafibot.py --help
"@ -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "OK - venv is ready:" -ForegroundColor Green
Write-Host '  .\.venv\Scripts\Activate.ps1' -ForegroundColor White
Write-Host '  python .\mafibot.py ui' -ForegroundColor White
