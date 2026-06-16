# Scan video files and report video codec distribution (metadata-only via ffprobe).
# Usage: .\Get-VideoCodecs.ps1
#        .\Get-VideoCodecs.ps1 -Path Y:\ -ThrottleLimit 12
#        .\Get-VideoCodecs.ps1 -ReportOnly -Path Y:\
#        .\Get-VideoCodecs.ps1 -ReportOnly -OpenHtml
#        .\Get-VideoCodecs.ps1 -Path Y:\ -OutputCsv Y:\custom-report.csv
#
# Run without parameters to be prompted for options interactively.
# If -Path is omitted, you will be prompted. CSV/HTML default to the scan folder
# (codec-report.csv / codec-report.html) unless you specify otherwise.

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string] $Path,
    [string] $OutputCsv,
    [string] $OutputHtml,
    [string] $Ffprobe,
    [ValidateRange(1, 64)]
    [int] $ThrottleLimit = 12,
    [switch] $ReportOnly,
    [switch] $NoHtml,
    [switch] $OpenHtml
)

function Get-FfprobeFromPathEnv {
    $cmd = Get-Command ffprobe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

if (-not $PSBoundParameters.ContainsKey('Ffprobe')) {
    $Ffprobe = Get-FfprobeFromPathEnv
    if (-not $Ffprobe) { $Ffprobe = 'ffprobe' }
}

$ScriptBoundParameters = $PSBoundParameters

$VideoExtensions = @('.mp4', '.mkv', '.m4v', '.mov', '.webm', '.avi', '.wmv', '.flv', '.ts', '.m2ts')

function Get-SuggestedScanPath {
    if (Test-Path -LiteralPath 'Y:\') { return 'Y:\' }
    return (Get-Location).ProviderPath
}

function Get-DefaultOutputPaths {
    param([string] $ScanPath)
    $root = $ScanPath.TrimEnd('\')
    @{
        Csv  = Join-Path $root 'codec-report.csv'
        Html = Join-Path $root 'codec-report.html'
    }
}

function Resolve-ScanConfiguration {
    if (-not $ScriptBoundParameters.ContainsKey('Path') -or [string]::IsNullOrWhiteSpace($Path)) {
        $label = if ($ReportOnly) { 'Scanned folder' } else { 'Folder to scan' }
        $script:Path = Read-HostPath -Prompt $label -Default (Get-SuggestedScanPath) -MustExist
    }

    $defaults = Get-DefaultOutputPaths $Path
    if (-not $ScriptBoundParameters.ContainsKey('OutputCsv') -or [string]::IsNullOrWhiteSpace($OutputCsv)) {
        $script:OutputCsv = $defaults.Csv
    }
    if (-not $ScriptBoundParameters.ContainsKey('OutputHtml') -or [string]::IsNullOrWhiteSpace($OutputHtml)) {
        $script:OutputHtml = $defaults.Html
    }
}

function Read-YesNo {
    param(
        [string] $Prompt,
        [bool] $DefaultYes = $false
    )
    $hint = if ($DefaultYes) { '[Y/n]' } else { '[y/N]' }
    while ($true) {
        $response = Read-Host "$Prompt $hint"
        if ([string]::IsNullOrWhiteSpace($response)) { return $DefaultYes }
        if ($response -match '^[Yy](es)?$') { return $true }
        if ($response -match '^[Nn](o)?$') { return $false }
        Write-Host 'Please enter Y or N.'
    }
}

function Read-HostDefault {
    param(
        [string] $Prompt,
        [string] $Default
    )
    $response = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($response)) { return $Default }
    return $response.Trim()
}

function Read-HostPath {
    param(
        [string] $Prompt,
        [string] $Default,
        [switch] $MustExist
    )
    while ($true) {
        $value = Read-HostDefault -Prompt $Prompt -Default $Default
        if (-not $MustExist -or (Test-Path -LiteralPath $value)) { return $value }
        Write-Host "Path not found: $value" -ForegroundColor Yellow
    }
}

function Read-HostInt {
    param(
        [string] $Prompt,
        [int] $Default,
        [int] $Min = [int]::MinValue,
        [int] $Max = [int]::MaxValue
    )
    while ($true) {
        $raw = Read-HostDefault -Prompt $Prompt -Default ([string]$Default)
        if ($raw -match '^\d+$' -and [int]$raw -ge $Min -and [int]$raw -le $Max) {
            return [int]$raw
        }
        Write-Host "Please enter a whole number from $Min to $Max."
    }
}

function Initialize-InteractiveOptions {
    Write-Host ''
    Write-Host '========================================' -ForegroundColor Cyan
    Write-Host '  Video Codec Scanner' -ForegroundColor Cyan
    Write-Host '========================================' -ForegroundColor Cyan
    Write-Host ''
    Write-Host '  [1] Scan a folder for video codecs'
    Write-Host '  [2] Build report from existing CSV'
    Write-Host ''

    $action = Read-HostDefault -Prompt 'Choose action' -Default '1'
    if ($action -eq '2') {
        $script:ReportOnly = $true
        $script:Path = Read-HostPath -Prompt 'Scanned folder' -Default (Get-SuggestedScanPath) -MustExist
        $defaults = Get-DefaultOutputPaths $Path
        $script:OutputCsv = Read-HostPath -Prompt 'CSV report path' -Default $defaults.Csv -MustExist
        $script:NoHtml = -not (Read-YesNo -Prompt 'Generate HTML report?' -DefaultYes $true)
        if (-not $script:NoHtml) {
            $script:OutputHtml = Read-HostDefault -Prompt 'HTML report path' -Default $defaults.Html
            $script:OpenHtml = Read-YesNo -Prompt 'Open HTML in browser when done?' -DefaultYes $false
        }
        if (-not (Read-YesNo -Prompt 'Generate report now?' -DefaultYes $true)) {
            Write-Host 'Cancelled.'
            exit 0
        }
        return
    }

    $script:ReportOnly = $false
    $script:Path = Read-HostPath -Prompt 'Folder to scan' -Default (Get-SuggestedScanPath) -MustExist
    $defaults = Get-DefaultOutputPaths $Path
    $script:ThrottleLimit = Read-HostInt -Prompt 'Parallel ffprobe threads' -Default $ThrottleLimit -Min 1 -Max 64
    $script:OutputCsv = Read-HostDefault -Prompt 'CSV report path' -Default $defaults.Csv
    $script:NoHtml = -not (Read-YesNo -Prompt 'Generate HTML report?' -DefaultYes $true)
    if (-not $script:NoHtml) {
        $script:OutputHtml = Read-HostDefault -Prompt 'HTML report path' -Default $defaults.Html
        $script:OpenHtml = Read-YesNo -Prompt 'Open HTML in browser when done?' -DefaultYes $false
    }

    $script:Ffprobe = Read-HostDefault -Prompt 'ffprobe path' -Default $Ffprobe
    if (-not (Read-YesNo -Prompt "Start scanning $script:Path now?" -DefaultYes $false)) {
        Write-Host 'Cancelled.'
        exit 0
    }
}

if ($ScriptBoundParameters.Count -eq 0) {
    Initialize-InteractiveOptions
} else {
    Resolve-ScanConfiguration
}

function Format-SizeGB([long] $Bytes) {
    [math]::Round($Bytes / 1GB, 3)
}

function Format-DisplaySize([double] $GB) {
    if ($GB -ge 1024) { return '{0:N2} TB' -f ($GB / 1024) }
    return '{0:N2} GB' -f $GB
}

function Get-CodecDisplayName([string] $Codec) {
    switch ($Codec.ToLowerInvariant()) {
        'av1' { 'AV1' }
        'h264' { 'H.264' }
        'hevc' { 'HEVC' }
        'vp9' { 'VP9' }
        'vp8' { 'VP8' }
        'mpeg4' { 'MPEG-4' }
        'mpeg2video' { 'MPEG-2' }
        'mjpeg' { 'MJPEG' }
        'prores' { 'ProRes' }
        'no_video' { 'No video stream' }
        'error' { 'Probe error' }
        default { $Codec }
    }
}

function Normalize-Codec([string] $Raw) {
    if ([string]::IsNullOrWhiteSpace($Raw)) { return 'no_video' }
    $codec = $Raw.Trim().TrimEnd(',').Trim().ToLowerInvariant()
    if ($codec -match '\s') { $codec = ($codec -split '\s+', 2)[0] }
    if ([string]::IsNullOrWhiteSpace($codec)) { return 'no_video' }
    return $codec
}

function Resolve-FfprobePath([string] $Candidate) {
    if ($Candidate -and (Test-Path -LiteralPath $Candidate)) {
        return (Resolve-Path -LiteralPath $Candidate).ProviderPath
    }
    $fromPath = Get-FfprobeFromPathEnv
    if ($fromPath) { return $fromPath }
    throw "ffprobe not found. Install FFmpeg or pass -Ffprobe with a valid path."
}

function Get-VideoCodecResult {
    param(
        [string] $FilePath,
        [long] $SizeBytes,
        [string] $Extension,
        [string] $ProbeExe
    )

    $codec = 'error'
    try {
        $raw = & $ProbeExe -v error -select_streams v:0 `
            -show_entries stream=codec_name -of csv=p=0 `
            -- $FilePath 2>$null
        if ($LASTEXITCODE -eq 0) {
            $codec = Normalize-Codec $raw
        }
    } catch {
        $codec = 'error'
    }

    [PSCustomObject]@{
        Path      = $FilePath
        Codec     = $codec
        SizeGB    = Format-SizeGB $SizeBytes
        Extension = $Extension
    }
}

function ConvertTo-HtmlSafe {
    param([AllowNull()][object] $Value)
    if ($null -eq $Value) { return '' }
    return [System.Net.WebUtility]::HtmlEncode([string]$Value)
}

function Get-NormalizedResults([object[]] $Results) {
    foreach ($row in $Results) {
        [PSCustomObject]@{
            Path      = $row.Path
            Codec     = Normalize-Codec $row.Codec
            SizeGB    = [double]$row.SizeGB
            Extension = if ($row.Extension) { $row.Extension.ToLowerInvariant() } else {
                [System.IO.Path]::GetExtension($row.Path).ToLowerInvariant()
            }
        }
    }
}

function Get-CodecCssClass([string] $Codec) {
    switch ($Codec.ToLowerInvariant()) {
        'av1' { 'av1' }
        'h264' { 'h264' }
        'hevc' { 'hevc' }
        'vp9' { 'vp9' }
        'vp8' { 'vp8' }
        'error' { 'error' }
        default { 'other' }
    }
}

function New-CodecHtmlReport {
    param(
        [object[]] $Results,
        [string] $ScanPath,
        [string] $OutputPath
    )

    $normalized = @(Get-NormalizedResults $Results)
    $generatedAt = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $total = $normalized.Count
    $totalGB = ($normalized | Measure-Object -Property SizeGB -Sum).Sum
    $av1Rows = @($normalized | Where-Object { $_.Codec -eq 'av1' })
    $nonAv1Rows = @($normalized | Where-Object { $_.Codec -ne 'av1' })
    $av1GB = ($av1Rows | Measure-Object -Property SizeGB -Sum).Sum
    $nonAv1GB = ($nonAv1Rows | Measure-Object -Property SizeGB -Sum).Sum
    $av1Pct = if ($total -gt 0) { [math]::Round(100 * $av1Rows.Count / $total, 1) } else { 0 }
    $av1SizePct = if ($totalGB -gt 0) { [math]::Round(100 * $av1GB / $totalGB, 1) } else { 0 }

    $codecGroups = $normalized | Group-Object Codec | Sort-Object Count -Descending
    $extGroups = $normalized | Group-Object Extension | Sort-Object Count -Descending

    $codecRows = ($codecGroups | ForEach-Object {
        $groupGB = ($_.Group | Measure-Object -Property SizeGB -Sum).Sum
        $pct = if ($total -gt 0) { [math]::Round(100 * $_.Count / $total, 1) } else { 0 }
        $sizePct = if ($totalGB -gt 0) { [math]::Round(100 * $groupGB / $totalGB, 1) } else { 0 }
        $label = Get-CodecDisplayName $_.Name
        $css = Get-CodecCssClass $_.Name
        @"
<tr>
  <td><span class="pill $css">$((ConvertTo-HtmlSafe $label))</span></td>
  <td class="num">$($_.Count)</td>
  <td class="num">$((Format-DisplaySize $groupGB))</td>
  <td class="num">$pct%</td>
  <td>
    <div class="bar-track"><div class="bar-fill $css" style="width:${pct}%"></div></div>
    <span class="bar-label">$sizePct% of storage</span>
  </td>
</tr>
"@
    }) -join "`n"

    $extRows = ($extGroups | ForEach-Object {
        $groupGB = ($_.Group | Measure-Object -Property SizeGB -Sum).Sum
        $pct = if ($total -gt 0) { [math]::Round(100 * $_.Count / $total, 1) } else { 0 }
        @"
<tr>
  <td>$((ConvertTo-HtmlSafe $_.Name))</td>
  <td class="num">$($_.Count)</td>
  <td class="num">$((Format-DisplaySize $groupGB))</td>
  <td class="num">$pct%</td>
</tr>
"@
    }) -join "`n"

    $codecOptions = ($codecGroups | ForEach-Object {
        $label = Get-CodecDisplayName $_.Name
        "<option value=""$((ConvertTo-HtmlSafe $_.Name))"">$((ConvertTo-HtmlSafe $label)) ($($_.Count))</option>"
    }) -join "`n"

    $fileRows = ($normalized | Sort-Object Codec, Path | ForEach-Object {
        $label = Get-CodecDisplayName $_.Codec
        $css = Get-CodecCssClass $_.Codec
        $fileName = [System.IO.Path]::GetFileName($_.Path)
        $dirName = [System.IO.Path]::GetDirectoryName($_.Path)
        @"
<tr data-codec="$((ConvertTo-HtmlSafe $_.Codec))" data-search="$((ConvertTo-HtmlSafe ($_.Path.ToLowerInvariant())))">
  <td><span class="pill $css">$((ConvertTo-HtmlSafe $label))</span></td>
  <td class="num">$((Format-DisplaySize $_.SizeGB))</td>
  <td>$((ConvertTo-HtmlSafe $_.Extension))</td>
  <td class="file-name" title="$((ConvertTo-HtmlSafe $_.Path))">$((ConvertTo-HtmlSafe $fileName))</td>
  <td class="file-path muted">$((ConvertTo-HtmlSafe $dirName))</td>
</tr>
"@
    }) -join "`n"

    $html = @"
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Video Codec Report — $((ConvertTo-HtmlSafe $ScanPath))</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0d1117;
      --panel: #151b23;
      --text: #e5edf6;
      --muted: #95a3b8;
      --accent: #67e8f9;
      --border: #303b4d;
      --av1: #34d399;
      --h264: #60a5fa;
      --hevc: #a78bfa;
      --vp9: #f472b6;
      --vp8: #fb923c;
      --error: #fb7185;
      --other: #94a3b8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(circle at top left, #134e4a 0, var(--bg) 36rem);
      color: var(--text);
      font-family: "Segoe UI", Arial, sans-serif;
      line-height: 1.45;
    }
    main { max-width: 1480px; margin: 0 auto; padding: 32px; }
    header { margin-bottom: 28px; }
    h1 { margin: 0 0 8px; font-size: 2.1rem; letter-spacing: -0.04em; }
    h2 { margin: 28px 0 12px; font-size: 1.2rem; }
    .muted { color: var(--muted); }
    .meta, .cards { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); }
    .card, .panel, .split-card {
      background: rgba(21, 27, 35, 0.9);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.22);
    }
    .card { padding: 16px; }
    .card span { display: block; color: var(--muted); font-size: 0.86rem; }
    .card strong { display: block; margin-top: 8px; font-size: 1.45rem; color: var(--accent); }
    .card.av1 strong { color: var(--av1); }
    .card.nonav1 strong { color: var(--h264); }
    .split-card { padding: 20px; margin-bottom: 8px; }
    .split-header { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 12px; font-size: 0.95rem; }
    .split-bar { display: flex; height: 18px; border-radius: 999px; overflow: hidden; background: rgba(15, 23, 42, 0.9); border: 1px solid var(--border); }
    .split-bar .av1 { background: linear-gradient(90deg, #059669, var(--av1)); }
    .split-bar .nonav1 { background: linear-gradient(90deg, #2563eb, var(--h264)); }
    .panel { overflow: hidden; margin-bottom: 8px; }
    .controls { display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 12px; }
    .controls input, .controls select {
      min-width: 220px;
      background: rgba(15, 23, 42, 0.9);
      color: var(--text);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 9px 11px;
      outline: none;
    }
    .controls input:focus, .controls select:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(103, 232, 249, 0.12);
    }
    .table-status { align-self: center; color: var(--muted); font-size: 0.9rem; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 11px 12px; border-bottom: 1px solid var(--border); vertical-align: top; text-align: left; }
    th { color: var(--muted); font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.04em; background: rgba(15, 23, 42, 0.55); position: sticky; top: 0; }
    .num { font-variant-numeric: tabular-nums; white-space: nowrap; }
    .file-name { max-width: 320px; word-break: break-word; }
    .file-path { max-width: 420px; word-break: break-all; font-size: 0.88rem; }
    .pill {
      display: inline-block;
      padding: 3px 10px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 600;
      letter-spacing: 0.02em;
      border: 1px solid transparent;
    }
    .pill.av1 { color: #6ee7b7; background: rgba(52, 211, 153, 0.12); border-color: rgba(52, 211, 153, 0.28); }
    .pill.h264 { color: #93c5fd; background: rgba(96, 165, 250, 0.12); border-color: rgba(96, 165, 250, 0.28); }
    .pill.hevc { color: #c4b5fd; background: rgba(167, 139, 250, 0.12); border-color: rgba(167, 139, 250, 0.28); }
    .pill.vp9 { color: #f9a8d4; background: rgba(244, 114, 182, 0.12); border-color: rgba(244, 114, 182, 0.28); }
    .pill.vp8 { color: #fdba74; background: rgba(251, 146, 60, 0.12); border-color: rgba(251, 146, 60, 0.28); }
    .pill.error { color: #fda4af; background: rgba(251, 113, 133, 0.12); border-color: rgba(251, 113, 133, 0.28); }
    .pill.other { color: #cbd5e1; background: rgba(148, 163, 184, 0.12); border-color: rgba(148, 163, 184, 0.28); }
    .bar-track { height: 8px; background: rgba(15, 23, 42, 0.9); border-radius: 999px; overflow: hidden; border: 1px solid var(--border); }
    .bar-fill { height: 100%; border-radius: 999px; }
    .bar-fill.av1 { background: linear-gradient(90deg, #059669, var(--av1)); }
    .bar-fill.h264 { background: linear-gradient(90deg, #2563eb, var(--h264)); }
    .bar-fill.hevc { background: linear-gradient(90deg, #7c3aed, var(--hevc)); }
    .bar-fill.error { background: linear-gradient(90deg, #e11d48, var(--error)); }
    .bar-fill.other { background: linear-gradient(90deg, #475569, var(--other)); }
    .bar-label { display: block; margin-top: 6px; color: var(--muted); font-size: 0.8rem; }
    .grid-2 { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); }
    #file-table-wrap { max-height: 70vh; overflow: auto; }
    tr.hidden { display: none; }
    footer { margin-top: 28px; color: var(--muted); font-size: 0.86rem; }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Video Codec Report</h1>
      <p class="muted">Scanned <strong>$((ConvertTo-HtmlSafe $ScanPath))</strong> on $generatedAt</p>
    </header>

    <section class="cards">
      <div class="card"><span>Total files</span><strong>$total</strong></div>
      <div class="card"><span>Total size</span><strong>$((Format-DisplaySize $totalGB))</strong></div>
      <div class="card av1"><span>AV1 files</span><strong>$($av1Rows.Count)</strong></div>
      <div class="card nonav1"><span>Non-AV1 files</span><strong>$($nonAv1Rows.Count)</strong></div>
      <div class="card"><span>Codecs found</span><strong>$($codecGroups.Count)</strong></div>
      <div class="card"><span>Extensions</span><strong>$($extGroups.Count)</strong></div>
    </section>

    <section class="split-card">
      <div class="split-header">
        <span><strong style="color:var(--av1)">AV1</strong> — $($av1Rows.Count) files ($((Format-DisplaySize $av1GB)))</span>
        <span><strong style="color:var(--h264)">Non-AV1</strong> — $($nonAv1Rows.Count) files ($((Format-DisplaySize $nonAv1GB)))</span>
      </div>
      <div class="split-bar" title="$av1Pct% of files are AV1">
        <div class="av1" style="width:${av1Pct}%"></div>
        <div class="nonav1" style="width:$([math]::Round(100 - $av1Pct, 1))%"></div>
      </div>
      <p class="muted" style="margin:10px 0 0;font-size:0.9rem;">$av1Pct% of files · $av1SizePct% of storage is AV1</p>
    </section>

    <div class="grid-2">
      <section>
        <h2>By codec</h2>
        <div class="panel table-wrap">
          <table>
            <thead><tr><th>Codec</th><th>Files</th><th>Size</th><th>% files</th><th>Share</th></tr></thead>
            <tbody>$codecRows</tbody>
          </table>
        </div>
      </section>
      <section>
        <h2>By extension</h2>
        <div class="panel table-wrap">
          <table>
            <thead><tr><th>Ext</th><th>Files</th><th>Size</th><th>% files</th></tr></thead>
            <tbody>$extRows</tbody>
          </table>
        </div>
      </section>
    </div>

    <section>
      <h2>All files</h2>
      <div class="controls">
        <input id="search" type="search" placeholder="Search path or filename..." aria-label="Search files">
        <select id="codec-filter" aria-label="Filter by codec">
          <option value="">All codecs</option>
          $codecOptions
        </select>
        <span id="table-status" class="table-status">Showing $total of $total</span>
      </div>
      <div id="file-table-wrap" class="panel table-wrap">
        <table id="file-table">
          <thead><tr><th>Codec</th><th>Size</th><th>Ext</th><th>Filename</th><th>Directory</th></tr></thead>
          <tbody>$fileRows</tbody>
        </table>
      </div>
    </section>

    <footer>Generated by Get-VideoCodecs.ps1 · metadata-only scan via ffprobe</footer>
  </main>
  <script>
    const search = document.getElementById('search');
    const codecFilter = document.getElementById('codec-filter');
    const rows = Array.from(document.querySelectorAll('#file-table tbody tr'));
    const status = document.getElementById('table-status');

    function applyFilters() {
      const q = (search.value || '').trim().toLowerCase();
      const codec = codecFilter.value;
      let visible = 0;
      for (const row of rows) {
        const matchSearch = !q || row.dataset.search.includes(q);
        const matchCodec = !codec || row.dataset.codec === codec;
        const show = matchSearch && matchCodec;
        row.classList.toggle('hidden', !show);
        if (show) visible++;
      }
      status.textContent = 'Showing ' + visible.toLocaleString() + ' of ' + rows.length.toLocaleString();
    }

    search.addEventListener('input', applyFilters);
    codecFilter.addEventListener('change', applyFilters);
  </script>
</body>
</html>
"@

    $outputDir = Split-Path -Parent $OutputPath
    if ($outputDir -and -not (Test-Path -LiteralPath $outputDir)) {
        New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    }
    [System.IO.File]::WriteAllText($OutputPath, $html, [System.Text.UTF8Encoding]::new($false))
    return $OutputPath
}

function Export-CodecHtml {
    param(
        [object[]] $Results,
        [string] $ScanPath,
        [string] $OutputPath
    )

    $path = New-CodecHtmlReport -Results $Results -ScanPath $ScanPath -OutputPath $OutputPath
    Write-Host "Wrote HTML report: $path"
    return $path
}

function Show-CodecSummary([object[]] $Results) {
    $normalized = @(Get-NormalizedResults $Results)
    $total = $normalized.Count
    $totalGB = ($normalized | Measure-Object -Property SizeGB -Sum).Sum

    Write-Host ''
    Write-Host "=== Codec Summary ($total video files, $(Format-DisplaySize $totalGB) total) ==="

    $groups = $normalized | Group-Object Codec | Sort-Object Count -Descending
    foreach ($group in $groups) {
        $groupGB = ($group.Group | Measure-Object -Property SizeGB -Sum).Sum
        $label = Get-CodecDisplayName $group.Name
        Write-Host ('{0,-16} {1,6} files  ({2})' -f "${label}:", $group.Count, (Format-DisplaySize $groupGB))
    }

    $av1 = $normalized | Where-Object { $_.Codec -eq 'av1' }
    $nonAv1 = $normalized | Where-Object { $_.Codec -ne 'av1' }
    $av1GB = ($av1 | Measure-Object -Property SizeGB -Sum).Sum
    $nonAv1GB = ($nonAv1 | Measure-Object -Property SizeGB -Sum).Sum

    Write-Host ''
    Write-Host '=== AV1 vs non-AV1 ==='
    Write-Host ('AV1:     {0,6} files  ({1})' -f $av1.Count, (Format-DisplaySize $av1GB))
    Write-Host ('Non-AV1: {0,6} files  ({1})' -f $nonAv1.Count, (Format-DisplaySize $nonAv1GB))
    Write-Host ''
}

function Invoke-CodecReportOutput {
    param(
        [object[]] $Results,
        [string] $ScanPath
    )

    Show-CodecSummary $Results
    Write-Host "CSV report: $OutputCsv"

    if (-not $NoHtml) {
        $htmlPath = Export-CodecHtml -Results $Results -ScanPath $ScanPath -OutputPath $OutputHtml
        if ($OpenHtml) {
            Start-Process $htmlPath
        }
    }
}

$ffprobePath = Resolve-FfprobePath $Ffprobe

if ($ReportOnly) {
    if (-not (Test-Path -LiteralPath $OutputCsv)) {
        throw "Report file not found: $OutputCsv"
    }
    $results = Import-Csv -LiteralPath $OutputCsv
    $scanPath = if (Test-Path -LiteralPath $Path) { $Path } else {
        $first = ($results | Select-Object -First 1).Path
        if ($first) { Split-Path -Parent $first } else { '.' }
    }
    Invoke-CodecReportOutput -Results $results -ScanPath $scanPath
    return
}

if (-not (Test-Path -LiteralPath $Path)) {
    throw "Path not found: $Path"
}

$existing = @{}
if (Test-Path -LiteralPath $OutputCsv) {
    Import-Csv -LiteralPath $OutputCsv | ForEach-Object { $existing[$_.Path] = $_ }
    Write-Host "Resuming from existing report ($($existing.Count) files already probed)."
}

Write-Host "Enumerating video files under $Path ..."
$swEnum = [System.Diagnostics.Stopwatch]::StartNew()
$videoFiles = Get-ChildItem -LiteralPath $Path -File -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $VideoExtensions -contains $_.Extension.ToLowerInvariant() }
$swEnum.Stop()
Write-Host ("Found {0} video files in {1:N1}s." -f $videoFiles.Count, $swEnum.Elapsed.TotalSeconds)

$pending = foreach ($file in $videoFiles) {
    if (-not $existing.ContainsKey($file.FullName)) { $file }
}

if ($pending.Count -eq 0) {
    Write-Host 'No new files to probe.'
    $allResults = $existing.Values
} else {
    Write-Host ("Probing {0} files with ffprobe (ThrottleLimit {1}) ..." -f $pending.Count, $ThrottleLimit)
    $swProbe = [System.Diagnostics.Stopwatch]::StartNew()
    $probed = $pending | ForEach-Object -Parallel {
        function Format-SizeGB([long] $Bytes) { [math]::Round($Bytes / 1GB, 3) }
        function Normalize-Codec([string] $Raw) {
            if ([string]::IsNullOrWhiteSpace($Raw)) { return 'no_video' }
            $codec = $Raw.Trim().TrimEnd(',').Trim().ToLowerInvariant()
            if ($codec -match '\s') { $codec = ($codec -split '\s+', 2)[0] }
            if ([string]::IsNullOrWhiteSpace($codec)) { return 'no_video' }
            return $codec
        }

        $codec = 'error'
        try {
            $raw = & $using:ffprobePath -v error -select_streams v:0 `
                -show_entries stream=codec_name -of csv=p=0 `
                -- $_.FullName 2>$null
            if ($LASTEXITCODE -eq 0) { $codec = Normalize-Codec $raw }
        } catch {
            $codec = 'error'
        }

        [PSCustomObject]@{
            Path      = $_.FullName
            Codec     = $codec
            SizeGB    = Format-SizeGB $_.Length
            Extension = $_.Extension.ToLowerInvariant()
        }
    } -ThrottleLimit $ThrottleLimit
    $swProbe.Stop()

    $rate = if ($swProbe.Elapsed.TotalSeconds -gt 0) { $pending.Count / $swProbe.Elapsed.TotalSeconds } else { 0 }
    Write-Host ("Probed {0} files in {1:N1}s ({2:N1} files/sec)." -f $pending.Count, $swProbe.Elapsed.TotalSeconds, $rate)

    $allResults = @($existing.Values) + @($probed)
}

$outputDir = Split-Path -Parent $OutputCsv
if ($outputDir -and -not (Test-Path -LiteralPath $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$allResults | Sort-Object Path | Export-Csv -LiteralPath $OutputCsv -NoTypeInformation -Encoding UTF8
Write-Host "Wrote report: $OutputCsv"

Invoke-CodecReportOutput -Results $allResults -ScanPath $Path
