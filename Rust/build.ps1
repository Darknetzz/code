Set-Location -Path $PSScriptRoot

$BuildDirs = @("pathman", "dns-net-check", "prereq-doctor")

foreach ($BuildDir in $BuildDirs) {
    Set-Location -Path $BuildDir
    cargo build --release
    Set-Location -Path $PSScriptRoot
}