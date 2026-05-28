param(
    [string[]]$Projects = @("av1", "pytree", "otherproj")
)

foreach ($proj in $Projects) {
    Write-Host "====================================="
    Write-Host "Building Python project: $proj"
    Write-Host "====================================="

    $projPath = Join-Path -Path $PSScriptRoot -ChildPath $proj

    if (-not (Test-Path $projPath)) {
        Write-Warning "Project path '$projPath' does not exist. Skipping."
        continue
    }

    Push-Location $projPath

    # Check if pybin.exe is in PATH
    if (-not (Get-Command pybin.exe -ErrorAction SilentlyContinue)) {
        Write-Host "Error: 'pybin.exe' not found in PATH. Please ensure it is installed and try again." -ForegroundColor Red
        exit 1
    }

    pybin.exe build
    if ($LastExitCode -ne 0) {
        Write-Host "Build failed for $proj" -ForegroundColor Red
    } else {
        Write-Host "Build succeeded for $proj" -ForegroundColor Green
    }

    Pop-Location
}