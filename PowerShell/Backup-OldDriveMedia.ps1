#Requires -Version 5.1
<#
.SYNOPSIS
    Recursively scans an older drive for photos, videos, audio, and document files,
    reports counts and sizes, and optionally copies matches to a newer drive.

.DESCRIPTION
    The source tree is only read (enumeration and, if you confirm, copy reads).
    Nothing on the source is ever written, deleted, moved, or renamed by this script.

    If you omit parameters, the script prompts for paths and mode, shows a summary,
    and asks for confirmation before scanning, before writing a CSV, and before
    copying any file.

.PARAMETER SourceRoot
    Root of the old external drive or folder (e.g. E:\). Prompted if omitted.

.PARAMETER DestinationRoot
    Root on the new drive where files are copied. Prompted when copy is chosen.

.PARAMETER ScanOnly
    Only enumerate and report; do not copy. If neither this nor DestinationRoot is set,
    you will be asked.

.PARAMETER IncludeImages
    Include image extensions (default: true).

.PARAMETER IncludeVideos
    Include video extensions (default: true).

.PARAMETER IncludeAudio
    Include audio extensions (default: true).

.PARAMETER IncludeDocuments
    Include text/document extensions (default: true).

.PARAMETER SkipReparsePoints
    When true, excludes reparse-point items during recursion (default: true).

.PARAMETER ExportCsvPath
    If set, you will be asked to confirm before writing this CSV (not on the source).

.PARAMETER DryRunCopy
    If set, after you confirm, the script simulates copy counts without writing files
    (still requires confirmation before this step).

.EXAMPLE
    .\Backup-OldDriveMedia.ps1
    Prompts for paths and confirmations.

.EXAMPLE
    .\Backup-OldDriveMedia.ps1 -SourceRoot 'E:\' -ScanOnly
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string] $SourceRoot,

    [Parameter(Mandatory = $false)]
    [string] $DestinationRoot,

    [switch] $ScanOnly,

    [bool] $IncludeImages = $true,
    [bool] $IncludeVideos = $true,
    [bool] $IncludeAudio = $true,
    [bool] $IncludeDocuments = $true,

    [bool] $SkipReparsePoints = $true,

    [string] $ExportCsvPath,

    [switch] $DryRunCopy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Read-YesNo {
    param(
        [string] $Prompt,
        [bool] $DefaultYes = $false
    )
    $hint = if ($DefaultYes) { '[Y/n]' } else { '[y/N]' }
    while ($true) {
        $r = Read-Host "$Prompt $hint"
        if ([string]::IsNullOrWhiteSpace($r)) { return $DefaultYes }
        if ($r -match '^[Yy](es)?$') { return $true }
        if ($r -match '^[Nn](o)?$') { return $false }
        Write-Host 'Please enter Y or N.'
    }
}

function Get-MediaExtensionMap {
    $map = [ordered]@{}
    if ($IncludeImages) {
        foreach ($x in @(
                'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tif', 'tiff', 'heic', 'heif', 'webp',
                'raw', 'cr2', 'cr3', 'nef', 'nrw', 'arw', 'dng', 'orf', 'rw2', 'pef', 'srw',
                'svg', 'ico', 'psd', 'jfif', 'jpe'
            )) { $map[$x] = 'Image' }
    }
    if ($IncludeVideos) {
        foreach ($x in @(
                'mp4', 'm4v', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mpg', 'mpeg',
                '3gp', '3g2', 'mts', 'm2ts', 'ts', 'vob', 'asf', 'ogv', 'divx', 'f4v'
            )) { $map[$x] = 'Video' }
    }
    if ($IncludeAudio) {
        foreach ($x in @(
                'mp3', 'flac', 'wav', 'aac', 'm4a', 'ogg', 'oga', 'wma', 'opus', 'aiff', 'aif', 'alac', 'mpc'
            )) { $map[$x] = 'Audio' }
    }
    if ($IncludeDocuments) {
        foreach ($x in @(
                'txt', 'md', 'rtf', 'pdf', 'doc', 'docx', 'odt', 'log', 'csv', 'tsv',
                'json', 'xml', 'yaml', 'yml', 'ini', 'cfg', 'conf', 'eml', 'msg'
            )) { $map[$x] = 'Document' }
    }
    return $map
}

function Resolve-ExistingRoot {
    param([string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Path does not exist: $Path"
    }
    $item = Get-Item -LiteralPath $Path -ErrorAction Stop
    if (-not $item.PSIsContainer) {
        throw "Path must be a directory: $Path"
    }
    return $item.FullName
}

function Test-IsStrictDescendantPath {
    param(
        [string] $AncestorPrefix,
        [string] $Candidate
    )
    $a = $AncestorPrefix.TrimEnd('\') + '\'
    $c = $Candidate.TrimEnd('\')
    if ($c.Length -le $a.Length) { return $false }
    return $c.StartsWith($a, [System.StringComparison]::OrdinalIgnoreCase)
}

# --- Interactive: missing input ---
Write-Host ''
Write-Host '=== Old drive media — source is never modified (read-only) ===' -ForegroundColor Cyan
Write-Host ''

if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    $SourceRoot = Read-Host 'Source folder or drive root to scan (e.g. E:\ or E:\Users)'
}

$wantCopy = $false
if ($ScanOnly) {
    $wantCopy = $false
}
elseif (-not [string]::IsNullOrWhiteSpace($DestinationRoot)) {
    $wantCopy = $true
}
else {
    $wantCopy = Read-YesNo -Prompt 'After scanning, copy matching files to another drive?' -DefaultYes $false
}

if ($wantCopy -and [string]::IsNullOrWhiteSpace($DestinationRoot)) {
    $DestinationRoot = Read-Host 'Destination folder on the NEW drive (files are written ONLY here)'
}

if ($wantCopy -and [string]::IsNullOrWhiteSpace($DestinationRoot)) {
    throw 'Copy was selected but no destination path was provided.'
}

$SourceRoot = Resolve-ExistingRoot -Path $SourceRoot
$SourceRootPrefix = $SourceRoot
if (-not $SourceRootPrefix.EndsWith('\')) { $SourceRootPrefix += '\' }

if ($wantCopy) {
    if (-not (Test-Path -LiteralPath $DestinationRoot)) {
        if (Read-YesNo -Prompt "Destination does not exist yet:`n  $DestinationRoot`nCreate this folder on the destination drive?" -DefaultYes $true) {
            $null = New-Item -ItemType Directory -Path $DestinationRoot -Force -ErrorAction Stop
        }
        else {
            throw 'Destination must exist or be created before copy.'
        }
    }
    $null = Resolve-ExistingRoot -Path $DestinationRoot
    $DestinationRoot = (Get-Item -LiteralPath $DestinationRoot).FullName
    if (Test-IsStrictDescendantPath -AncestorPrefix $SourceRootPrefix -Candidate $DestinationRoot) {
        throw 'Destination cannot be inside the source tree. Choose a folder outside the source path.'
    }
    if ($SourceRootPrefix.TrimEnd('\').Equals($DestinationRoot.TrimEnd('\'), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Source and destination cannot be the same path.'
    }
}

$extToCategory = Get-MediaExtensionMap
if ($extToCategory.Count -eq 0) {
    throw 'All categories are disabled. Enable at least one of -IncludeImages, -IncludeVideos, -IncludeAudio, -IncludeDocuments.'
}

$cats = @($extToCategory.Values | Select-Object -Unique)
$includeBits = @(
    "Images: $IncludeImages",
    "Videos: $IncludeVideos",
    "Audio: $IncludeAudio",
    "Documents: $IncludeDocuments"
) -join '; '

# --- Summary ---
Write-Host ''
Write-Host '--- Summary (review before continuing) ---' -ForegroundColor Yellow
Write-Host "  Source (read-only):     $SourceRoot"
Write-Host '  Source will NOT be:     written to, deleted from, moved, or renamed.'
Write-Host "  Categories:             $($cats -join ', ')"
Write-Host "  Include flags:          $includeBits"
Write-Host "  Skip reparse points:    $SkipReparsePoints"
if (-not [string]::IsNullOrWhiteSpace($ExportCsvPath)) {
    Write-Host "  Export CSV to:          $ExportCsvPath"
}
else {
    Write-Host '  Export CSV:             (none)'
}
if ($wantCopy) {
    Write-Host "  Destination (writes):   $DestinationRoot"
    if ($DryRunCopy) {
        Write-Host '  Copy mode:              DRY RUN (no files written anywhere)'
    }
    else {
        Write-Host '  Copy mode:              copy files to destination after confirmation'
    }
}
else {
    Write-Host '  Copy:                   no (scan / report only)'
}

Write-Host ''
if (-not (Read-YesNo -Prompt 'Start the read-only scan now?' -DefaultYes $false)) {
    Write-Host 'Cancelled. No files were read beyond path checks.'
    return
}

# --- Scan (read-only on source) ---
$gciParams = @{
    LiteralPath = $SourceRoot
    File        = $true
    Recurse     = $true
    Force       = $true
    ErrorAction = 'SilentlyContinue'
}
if ($SkipReparsePoints) {
    $gciParams['Attributes'] = '!ReparsePoint'
}

Write-Host ''
Write-Host 'Enumerating files (read-only access to source; this may take a long time)...'

$counts = @{ Image = 0; Video = 0; Audio = 0; Document = 0 }
$bytes = @{ Image = [int64]0; Video = [int64]0; Audio = [int64]0; Document = [int64]0 }
$enumerateErrors = [System.Collections.ArrayList]::new()
$files = [System.Collections.ArrayList]::new()

$sw = [System.Diagnostics.Stopwatch]::StartNew()
$n = 0

Get-ChildItem @gciParams -ErrorVariable +enumerateErrors | ForEach-Object {
    $n++
    if (($n % 5000) -eq 0) {
        Write-Progress -Activity 'Scanning (read-only)' -Status "Files seen: $n" -PercentComplete -1
    }

    $ext = $_.Extension
    if ([string]::IsNullOrEmpty($ext)) { return }
    $key = $ext.TrimStart('.').ToLowerInvariant()
    if (-not $extToCategory.Contains($key)) { return }

    $cat = $extToCategory[$key]
    $counts[$cat]++
    $bytes[$cat] += $_.Length

    $null = $files.Add([pscustomobject]@{
            FullName      = $_.FullName
            Length        = $_.Length
            Category      = $cat
            LastWriteTime = $_.LastWriteTimeUtc
        })
}

Write-Progress -Activity 'Scanning (read-only)' -Completed
$sw.Stop()

Write-Host ("Enumeration finished in {0:n1} s. All files seen under source: {1}" -f $sw.Elapsed.TotalSeconds, $n)

$accessDenied = @($enumerateErrors | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] -and $_.CategoryInfo.Reason -eq 'UnauthorizedAccessException' })
if ($accessDenied.Count -gt 0) {
    Write-Warning "Some folders could not be read (access denied): $($accessDenied.Count) error(s). Run elevated or adjust permissions if you need those paths."
}

$totalFiles = ($counts.Values | Measure-Object -Sum).Sum
$totalBytes = ($bytes.Values | Measure-Object -Sum).Sum
Write-Host ''
Write-Host '--- Counts by category ---'
foreach ($k in @('Image', 'Video', 'Audio', 'Document')) {
    $includeCat = ($k -eq 'Image' -and $IncludeImages) -or ($k -eq 'Video' -and $IncludeVideos) -or ($k -eq 'Audio' -and $IncludeAudio) -or ($k -eq 'Document' -and $IncludeDocuments)
    if ($counts[$k] -gt 0 -or $includeCat) {
        $sz = if ($bytes[$k] -ge 1GB) { '{0:n2} GB' -f ($bytes[$k] / 1GB) } elseif ($bytes[$k] -ge 1MB) { '{0:n2} MB' -f ($bytes[$k] / 1MB) } else { '{0:n0} bytes' -f $bytes[$k] }
        Write-Host ("  {0,-10} files: {1,8}  size: {2}" -f $k, $counts[$k], $sz)
    }
}
Write-Host ("  {0,-10} files: {1,8}" -f 'TOTAL', $totalFiles)
if ($null -ne $totalBytes) {
    $ts = if ($totalBytes -ge 1GB) { '{0:n2} GB' -f ($totalBytes / 1GB) } else { '{0:n2} MB' -f ($totalBytes / 1MB) }
    Write-Host ("  {0,-10} size: {1}" -f 'TOTAL', $ts)
}

# --- CSV (writes only to ExportCsvPath, never to source) ---
if (-not [string]::IsNullOrWhiteSpace($ExportCsvPath)) {
    Write-Host ''
    if (-not (Read-YesNo -Prompt "Write CSV list to:`n  $ExportCsvPath`nProceed?" -DefaultYes $false)) {
        Write-Host 'CSV export skipped.'
    }
    else {
        $files | Export-Csv -LiteralPath $ExportCsvPath -NoTypeInformation -Encoding UTF8
        Write-Host "Exported CSV: $ExportCsvPath"
    }
}

if (-not $wantCopy) {
    Write-Host ''
    Write-Host 'Done. Source was not modified. No copy was requested.'
    return
}

# --- Copy (reads source, writes only to destination) ---
Write-Host ''
Write-Host '--- Copy step ---' -ForegroundColor Yellow
Write-Host "Matching files to copy: $totalFiles"
Write-Host "Destination: $DestinationRoot"
Write-Host 'The source will only be read; all writes go to the destination path above.'
if ($DryRunCopy) {
    if (-not (Read-YesNo -Prompt 'Run DRY RUN only (no files created or copied)?' -DefaultYes $false)) {
        Write-Host 'Copy/dry-run cancelled. Source was not modified.'
        return
    }
}
else {
    if (-not (Read-YesNo -Prompt 'Copy these files to the destination now?' -DefaultYes $false)) {
        Write-Host 'Copy cancelled. Source was not modified.'
        return
    }
}

$copyCount = 0
$copyBytes = [int64]0
$failures = [System.Collections.ArrayList]::new()

foreach ($f in $files) {
    $rel = $f.FullName.Substring($SourceRootPrefix.Length)
    $destPath = Join-Path -Path $DestinationRoot -ChildPath $rel
    $destDir = Split-Path -LiteralPath $destPath -Parent

    if ($DryRunCopy) {
        $copyCount++
        $copyBytes += $f.Length
        continue
    }

    if (-not (Test-Path -LiteralPath $destDir)) {
        $null = New-Item -ItemType Directory -Path $destDir -Force -ErrorAction Stop
    }

    try {
        Copy-Item -LiteralPath $f.FullName -Destination $destPath -Force -ErrorAction Stop
        $copyCount++
        $copyBytes += $f.Length
    }
    catch {
        $null = $failures.Add([pscustomobject]@{ Path = $f.FullName; Error = $_.Exception.Message })
    }
}

if ($DryRunCopy) {
    Write-Host "Dry run: would copy $copyCount files ($('{0:n2} GB' -f ($copyBytes / 1GB))). No files were written."
}
else {
    Write-Host "Copied $copyCount files. Source paths were not modified."
    if ($failures.Count -gt 0) {
        Write-Warning "Copy failures: $($failures.Count)"
        $failures | Select-Object -First 20 | Format-Table -AutoSize
    }
}
