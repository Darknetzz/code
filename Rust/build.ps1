Set-Location -Path $PSScriptRoot

$BuildDirs = @("rustdl", "pathman")

foreach ($BuildDir in $BuildDirs) {
    Set-Location -Path $BuildDir
    cargo build --release
    Set-Location -Path $PSScriptRoot
}