Set-Location -Path $PSScriptRoot

$BuildDirs = @("pathman", "dns-net-check", "prereq-doctor", "portscan", "pycrawl", "pytree", "lhp")

foreach ($BuildDir in $BuildDirs) {
    Set-Location -Path $BuildDir
    cargo build --release
    Set-Location -Path $PSScriptRoot
}