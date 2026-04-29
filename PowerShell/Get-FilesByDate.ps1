# Recursively list files under a directory, sorted by last modified time.
# Usage: .\Get-FilesByDate.ps1              # current directory
#        .\Get-FilesByDate.ps1 D:\Projects  # explicit path
#        .\Get-FilesByDate.ps1 -Descending  # newest first

param(
    [Parameter(Position = 0)]
    [string] $Path = '.',
    [switch] $Descending
)

Get-ChildItem -LiteralPath $Path -File -Recurse -ErrorAction SilentlyContinue |
    Sort-Object -Property LastWriteTime -Descending:$Descending
