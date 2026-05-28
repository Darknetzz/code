param(
    [string[]]$Projects,
    [switch]$Force
)

. (Join-Path -Path $PSScriptRoot -ChildPath 'build-common.ps1')

$rustRoot = Join-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -ChildPath 'Rust'

if (-not $Projects -or $Projects.Count -eq 0) {
    $Projects = Get-DiscoveredRustProjectNames -RustRoot $rustRoot
    Write-Host "Discovered $($Projects.Count) Rust project(s) with Cargo.toml: $($Projects -join ', ')" -ForegroundColor Cyan
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    Write-Host "Error: 'cargo' not found in PATH. Install Rust via https://rustup.rs/ and try again." -ForegroundColor Red
    exit 1
}

function Get-CargoReleaseExePaths {
    param([string]$ProjectPath)

    Push-Location $ProjectPath
    try {
        $metadataJson = cargo metadata --format-version 1 --no-deps 2>$null
        if (-not $metadataJson) {
            Write-Warning "cargo metadata failed for '$ProjectPath'."
            return @()
        }

        $metadata = $metadataJson | ConvertFrom-Json
        $package = $metadata.packages | Select-Object -First 1
        if (-not $package) {
            return @()
        }

        $binNames = @(
            $package.targets |
                Where-Object { $_.kind -contains 'bin' } |
                ForEach-Object { $_.name }
        )

        $exePaths = foreach ($name in $binNames) {
            $fileName = if ($IsWindows -or $env:OS -match 'Windows') { "$name.exe" } else { $name }
            Join-Path -Path $ProjectPath -ChildPath "target\release\$fileName"
        }

        return ,$exePaths
    }
    finally {
        Pop-Location
    }
}

function Get-RustSourceFiles {
    param([string]$ProjectPath)

    $paths = @(
        (Join-Path $ProjectPath 'Cargo.toml'),
        (Join-Path $ProjectPath 'Cargo.lock'),
        (Join-Path $ProjectPath 'build.rs')
    )

    $dirs = @(
        (Join-Path $ProjectPath 'src'),
        (Join-Path $ProjectPath 'build'),
        (Join-Path $ProjectPath '.cargo')
    )

    $files = foreach ($path in $paths) {
        if (Test-Path -LiteralPath $path) {
            Get-Item -LiteralPath $path
        }
    }

    foreach ($dir in $dirs) {
        if (Test-Path -LiteralPath $dir) {
            $files += Get-ChildItem -Path $dir -Recurse -File -ErrorAction SilentlyContinue
        }
    }

    return $files
}

function Test-RustProjectNeedsBuild {
    param(
        [string]$ProjectPath,
        [string[]]$ExePaths
    )

    if ($ExePaths.Count -eq 0) {
        return $true
    }

    foreach ($exePath in $ExePaths) {
        if (-not (Test-Path -LiteralPath $exePath)) {
            return $true
        }
    }

    $sourceFiles = Get-RustSourceFiles -ProjectPath $ProjectPath
    if ($sourceFiles.Count -eq 0) {
        return $true
    }

    $maxSourceTime = ($sourceFiles | Measure-Object -Property LastWriteTimeUtc -Maximum).Maximum

    foreach ($exePath in $ExePaths) {
        if ((Get-Item -LiteralPath $exePath).LastWriteTimeUtc -lt $maxSourceTime) {
            return $true
        }
    }

    return $false
}

foreach ($proj in $Projects) {
    Write-Host "====================================="
    Write-Host "Building Rust project: $proj"
    Write-Host "====================================="

    $projPath = Join-Path -Path $rustRoot -ChildPath $proj
    $cargoToml = Join-Path -Path $projPath -ChildPath 'Cargo.toml'

    if (-not (Test-Path -LiteralPath $projPath)) {
        Write-Warning "Project path '$projPath' does not exist. Skipping."
        continue
    }
    if (-not (Test-Path -LiteralPath $cargoToml)) {
        Write-Warning "Cargo.toml not found at '$cargoToml'. Skipping."
        continue
    }

    $exePaths = Get-CargoReleaseExePaths -ProjectPath $projPath
    if ($exePaths.Count -eq 0) {
        Write-Warning "No binary targets found for '$proj'. Skipping."
        continue
    }

    if (-not $Force -and -not (Test-RustProjectNeedsBuild -ProjectPath $projPath -ExePaths $exePaths)) {
        Write-Host "Up to date, skipping:" -ForegroundColor DarkGray
        foreach ($exePath in $exePaths) {
            Write-Host "  $exePath" -ForegroundColor DarkGray
        }
        continue
    }

    Push-Location $projPath
    cargo build --release
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Build failed for $proj" -ForegroundColor Red
    } else {
        Write-Host "Build succeeded for $proj" -ForegroundColor Green
        foreach ($exePath in $exePaths) {
            if (Test-Path -LiteralPath $exePath) {
                Write-Host "  $exePath" -ForegroundColor Green
            }
        }
    }
    Pop-Location
}
