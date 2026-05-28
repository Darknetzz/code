param(
    [string[]]$Projects = @("av1", "pytree", "pylink", "appkey-generator", "calculate-aspect-ratio", "pygallery"),
    [switch]$Force
)

$pythonRoot = Join-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -ChildPath "Python"

if (-not (Get-Command pybin.exe -ErrorAction SilentlyContinue)) {
    Write-Host "Error: 'pybin.exe' not found in PATH. Please ensure it is installed and try again." -ForegroundColor Red
    exit 1
}

function Get-ProjectExePath {
    param(
        [string]$ProjectPath,
        [string]$EntryScript
    )
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($EntryScript)
    Join-Path -Path $ProjectPath -ChildPath "dist\$stem.exe"
}

function Test-ProjectNeedsBuild {
    param(
        [string]$ProjectPath,
        [string]$ExePath
    )

    if (-not (Test-Path -LiteralPath $ExePath)) {
        return $true
    }

    $exeTime = (Get-Item -LiteralPath $ExePath).LastWriteTimeUtc
    $excludeTopLevel = @('dist', 'build', '__pycache__', '.venv', '.venv-build')

    $sourceFiles = Get-ChildItem -Path $ProjectPath -Recurse -File | Where-Object {
        $relative = $_.FullName.Substring($ProjectPath.Length).TrimStart('\', '/')
        $parts = $relative -split '[\\/]'
        if ($parts[0] -in $excludeTopLevel) { return $false }
        if ($parts -contains '__pycache__') { return $false }
        if ($_.Extension -eq '.pyc' -or $_.Name -like '*.spec.bak') { return $false }

        ($_.Extension -in '.py', '.spec') -or ($_.Name -eq 'requirements.txt')
    }

    foreach ($sourceFile in $sourceFiles) {
        if ($sourceFile.LastWriteTimeUtc -gt $exeTime) {
            return $true
        }
    }

    return $false
}

foreach ($proj in $Projects) {
    Write-Host "====================================="
    Write-Host "Building Python project: $proj"
    Write-Host "====================================="

    $projPath = Join-Path -Path $pythonRoot -ChildPath $proj
    $entryScript = Join-Path -Path $projPath -ChildPath "$proj.py"

    if (-not (Test-Path $projPath)) {
        Write-Warning "Project path '$projPath' does not exist. Skipping."
        continue
    }
    if (-not (Test-Path $entryScript)) {
        Write-Warning "Entry script '$entryScript' does not exist. Skipping."
        continue
    }

    $exePath = Get-ProjectExePath -ProjectPath $projPath -EntryScript $entryScript

    if (-not $Force -and -not (Test-ProjectNeedsBuild -ProjectPath $projPath -ExePath $exePath)) {
        Write-Host "Up to date, skipping: $exePath" -ForegroundColor DarkGray
        continue
    }

    Push-Location $projPath

    pybin.exe $entryScript
    if ($LastExitCode -ne 0) {
        Write-Host "Build failed for $proj" -ForegroundColor Red
    } else {
        Write-Host "Build succeeded for $proj" -ForegroundColor Green
    }

    Pop-Location
}