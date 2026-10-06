# Build pyredact.exe from a clean venv so PyInstaller does not pack the
# global site-packages (numpy/scipy/pyarrow/llvmlite/...).
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$venv = Join-Path $root ".venv-build"
$python = Join-Path $venv "Scripts\python.exe"
$dist = Join-Path $root "dist"
$exe = Join-Path $dist "pyredact.exe"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Creating build venv: $venv"
    python -m venv $venv
}

Write-Host "Installing build dependencies..."
& $python -m pip install -U pip
& $python -m pip install -r (Join-Path $root "requirements.txt")
& $python -m pip install "pyinstaller>=6.22.3"

Write-Host "Running PyInstaller..."
Push-Location $root
try {
    & $python -m PyInstaller --noconfirm --clean --distpath $dist pyredact.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Get-Item -LiteralPath $exe | Format-Table Name, @{ N = "MB"; E = { [math]::Round($_.Length / 1MB, 1) } }, LastWriteTime

$installed = Get-Command pyredact.exe -ErrorAction SilentlyContinue
if ($installed -and $installed.Source -ne $exe) {
    Write-Host "Copying to $($installed.Source)"
    Copy-Item -LiteralPath $exe -Destination $installed.Source -Force
}
