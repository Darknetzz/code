# Recursively list files under a directory, sorted by a chosen timestamp.
# Usage: .\Get-FilesByDate.ps1
#        .\Get-FilesByDate.ps1 D:\Projects -SortBy CreationTime -Descending

param(
    [Parameter(Position = 0)]
    [string] $Path = '.',
    [ValidateSet('LastWriteTime', 'CreationTime', 'LastAccessTime')]
    [string] $SortBy = 'LastWriteTime',
    [switch] $Descending
)

function Format-FileSize([long] $Bytes) {
    if ($Bytes -ge 1GB) { return '{0:N2} GB' -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return '{0:N2} MB' -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return '{0:N2} KB' -f ($Bytes / 1KB) }
    return "$Bytes B"
}

$dateHeader = switch ($SortBy) {
    'LastWriteTime' { 'Modified' }
    'CreationTime' { 'Created' }
    'LastAccessTime' { 'Accessed' }
}

Get-ChildItem -LiteralPath $Path -File -Recurse -ErrorAction SilentlyContinue |
    Sort-Object -Property $SortBy -Descending:$Descending |
    Select-Object @{ n = 'Path'; e = { $_.FullName } },
                  @{ n = 'Size'; e = { Format-FileSize $_.Length } },
                  @{ n = $dateHeader; e = { $_.($SortBy) } } |
    Format-Table -AutoSize
