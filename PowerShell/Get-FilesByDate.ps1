# Recursively list files under a directory, sorted by a chosen timestamp.
# Usage: .\Get-FilesByDate.ps1
#        .\Get-FilesByDate.ps1 D:\Projects -SortBy CreationTime -Descending
#        .\Get-FilesByDate.ps1 -Include *.ps1, *.md -First 20
#        .\Get-FilesByDate.ps1 -Include ps1, md, .log   # same as *.ps1, *.md, *.log

param(
    [Parameter(Position = 0)]
    [string] $Path = '.',
    [ValidateSet('LastWriteTime', 'CreationTime', 'LastAccessTime')]
    [string] $SortBy = 'LastWriteTime',
    [switch] $Descending,
    [string[]] $Include,
    [ValidateRange(0, [int]::MaxValue)]
    [int] $First = 0
)

function Format-FileSize([long] $Bytes) {
    if ($Bytes -ge 1GB) { return '{0:N2} GB' -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return '{0:N2} MB' -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return '{0:N2} KB' -f ($Bytes / 1KB) }
    return "$Bytes B"
}

function Normalize-IncludePatterns([string[]] $Patterns) {
    if (-not $Patterns) { return @() }
    $list = [System.Collections.Generic.List[string]]::new()
    foreach ($raw in $Patterns) {
        if ([string]::IsNullOrWhiteSpace($raw)) { continue }
        $t = $raw.Trim()
        if ($t -match '[*?]') { $list.Add($t); continue }
        if ($t.StartsWith('.')) { $list.Add("*$t"); continue }
        if ($t -match '^[^\\/:*?"<>|]+$') { $list.Add("*.$t"); continue }
        $list.Add($t)
    }
    return $list.ToArray()
}

$dateHeader = switch ($SortBy) {
    'LastWriteTime' { 'Modified' }
    'CreationTime' { 'Created' }
    'LastAccessTime' { 'Accessed' }
}

$resolved = (Resolve-Path -LiteralPath $Path).ProviderPath
$includeList = Normalize-IncludePatterns -Patterns $Include

if ($includeList.Count -gt 0) {
    $files = Get-ChildItem -Path (Join-Path $resolved '*') -File -Recurse -Include $includeList -ErrorAction SilentlyContinue
} else {
    $files = Get-ChildItem -LiteralPath $resolved -File -Recurse -ErrorAction SilentlyContinue
}

$sorted = $files | Sort-Object -Property $SortBy -Descending:$Descending
if ($First -gt 0) {
    $sorted = $sorted | Select-Object -First $First
}

$sorted |
    Select-Object @{ n = 'Path'; e = { $_.FullName } },
                  @{ n = 'Size'; e = { Format-FileSize $_.Length } },
                  @{ n = $dateHeader; e = { $_.($SortBy) } } |
    Format-Table -AutoSize
