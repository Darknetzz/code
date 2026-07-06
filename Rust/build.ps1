Set-Location -Path $PSScriptRoot

$BuildDirs = @(
    "pathman",
    "prereq-doctor",
    "rust-dns-net-check",
    "rust-hash-zero",
    "rust-portscan",
    "rust-crawl",
    "rust-sizetree",
    "rust-lhp"
)

foreach ($BuildDir in $BuildDirs) {
    Set-Location -Path $BuildDir
    cargo build --release
    Set-Location -Path $PSScriptRoot
}
