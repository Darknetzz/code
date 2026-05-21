# Build mafibot.exe (PyInstaller onefile + bundled Playwright Chromium).
# Run from anywhere:  .\build.ps1
# Reuse existing venv:  .\build.ps1 -SkipVenvSetup

param(
    [switch]$SkipVenvSetup,
    [switch]$SkipPlaywrightInstall,
    [string]$VenvDir = ".venv-build"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
Set-Location $Root

function Invoke-VenvPython {
    param([Parameter(Mandatory)][string[]]$Args)
    & (Join-Path $Root $VenvDir "Scripts" "python.exe") @Args
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "==> mafibot.exe build (root: $Root)" -ForegroundColor Cyan

if (-not $SkipVenvSetup) {
    $venvPython = Join-Path $Root $VenvDir "Scripts" "python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Host "==> Creating venv: $VenvDir" -ForegroundColor Cyan
        python -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }

    Write-Host "==> Installing dependencies" -ForegroundColor Cyan
    Invoke-VenvPython -Args @("-m", "pip", "install", "--upgrade", "pip")
    Invoke-VenvPython -Args @("-m", "pip", "install", "-r", "requirements.txt", "pyinstaller", "msvc-runtime")
    Invoke-VenvPython -Args @("-m", "pip", "install", "-e", (Join-Path $Root ".." "webbot"))
}

if (-not $SkipPlaywrightInstall) {
    Write-Host "==> Installing Playwright Chromium (PLAYWRIGHT_BROWSERS_PATH=0)" -ForegroundColor Cyan
    $env:PLAYWRIGHT_BROWSERS_PATH = "0"
    Invoke-VenvPython -Args @("-m", "playwright", "install", "chromium")
}

Write-Host "==> Ensuring msvc-runtime (greenlet / Playwright DLLs in frozen exe)" -ForegroundColor Cyan
Invoke-VenvPython -Args @("-m", "pip", "install", "msvc-runtime")

Write-Host "==> Running PyInstaller (mafibot.spec)" -ForegroundColor Cyan
$env:PLAYWRIGHT_BROWSERS_PATH = "0"
& (Join-Path $Root $VenvDir "Scripts" "pyinstaller.exe") mafibot.spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exe = Join-Path $Root "dist" "mafibot.exe"
if (-not (Test-Path $exe)) {
    Write-Error "Build finished but $exe was not found."
}
$sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host "==> Done: $exe ($sizeMb MB)" -ForegroundColor Green
Write-Host "    Smoke test: .\dist\mafibot.exe version" -ForegroundColor DarkGray
