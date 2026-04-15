#Requires -Version 5.1
<#
.SYNOPSIS
  Build gitt with version metadata (same ldflags as `make release`).

.PARAMETER Version
  Semantic version string injected into the binary (default: dev).

.PARAMETER Output
  Output executable name (default: gitt.exe).
#>
param(
    [string]$Version = "dev",
    [string]$Output = "gitt.exe"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$commit = "none"
try {
    $c = (& git rev-parse --short HEAD 2>$null)
    if ($LASTEXITCODE -eq 0 -and $c) { $commit = $c.Trim() }
} catch {
    # leave none
}

$buildDate = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$ldflags = "-X gitt/internal/version.Version=$Version -X gitt/internal/version.Commit=$commit -X gitt/internal/version.BuildDate=$buildDate"

& go build -ldflags $ldflags -o $Output .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Built $Output (version=$Version commit=$commit)"
