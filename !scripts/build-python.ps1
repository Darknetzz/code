param(
    [string[]]$Projects,
    [switch]$Force
)

. (Join-Path -Path $PSScriptRoot -ChildPath 'build-common.ps1')

$pythonRoot = Join-Path -Path (Split-Path -Path $PSScriptRoot -Parent) -ChildPath 'Python'

if (-not $Projects -or $Projects.Count -eq 0) {
    $Projects = Get-DiscoveredPythonProjectNames -PythonRoot $pythonRoot
    Write-Host "Discovered $($Projects.Count) Python project(s) with dist/: $($Projects -join ', ')" -ForegroundColor Cyan
}

if (-not (Get-Command pybin.exe -ErrorAction SilentlyContinue)) {
    Write-Host "Error: 'pybin.exe' not found in PATH. Please ensure it is installed and try again." -ForegroundColor Red
    exit 1
}

foreach ($proj in $Projects) {
    Write-Host "====================================="
    Write-Host "Building Python project: $proj"
    Write-Host "====================================="

    $projPath = Join-Path -Path $pythonRoot -ChildPath $proj

    if (-not (Test-Path -LiteralPath $projPath)) {
        Write-Warning "Project path '$projPath' does not exist. Skipping."
        continue
    }

    $customBuild = Join-Path -Path $projPath -ChildPath 'build.ps1'
    if (Test-Path -LiteralPath $customBuild) {
        $entryScripts = Get-PythonEntryScripts -ProjectPath $projPath -ProjectName $proj
        $needsBuild = $Force
        if (-not $needsBuild) {
            foreach ($entryScript in $entryScripts) {
                $exePath = Get-PythonExePath -ProjectPath $projPath -EntryScript $entryScript
                if (Test-PythonTargetNeedsBuild -ProjectPath $projPath -ExePath $exePath) {
                    $needsBuild = $true
                    break
                }
            }
        }

        if (-not $needsBuild) {
            Write-Host "Up to date, skipping custom build: $proj" -ForegroundColor DarkGray
            continue
        }

        Push-Location $projPath
        & $customBuild
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Build failed for $proj (custom build.ps1)" -ForegroundColor Red
        } else {
            Write-Host "Build succeeded for $proj (custom build.ps1)" -ForegroundColor Green
        }
        Pop-Location
        continue
    }

    $entryScripts = Get-PythonEntryScripts -ProjectPath $projPath -ProjectName $proj
    if ($entryScripts.Count -eq 0) {
        Write-Warning "No entry scripts found for '$proj'. Skipping."
        continue
    }

    foreach ($entryScript in $entryScripts) {
        $stem = [System.IO.Path]::GetFileName($entryScript)
        Write-Host "--- $stem ---"

        $exePath = Get-PythonExePath -ProjectPath $projPath -EntryScript $entryScript

        if (-not $Force -and -not (Test-PythonTargetNeedsBuild -ProjectPath $projPath -ExePath $exePath)) {
            Write-Host "Up to date, skipping: $exePath" -ForegroundColor DarkGray
            continue
        }

        Push-Location $projPath
        pybin.exe $entryScript
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Build failed for $proj ($stem)" -ForegroundColor Red
        } else {
            Write-Host "Build succeeded for $proj ($stem)" -ForegroundColor Green
        }
        Pop-Location
    }
}
