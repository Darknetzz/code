####################################################################
#   Info:
#   Collects and summarizes Windows Event Viewer entries.
#
#   Examples:
#     .\Analyze-EventLogs.ps1
#     .\Analyze-EventLogs.ps1 -DaysBack 7 -Output Terminal
#     .\Analyze-EventLogs.ps1 -DaysBack 14 -Output Html -OutputPath .\event-report.html
#     .\Analyze-EventLogs.ps1 -DaysBack 3 -Logs System,Application -Levels Critical,Error,Warning -Output Both
#
####################################################################

param(
    [Parameter()]
    [ValidateRange(1, 3650)]
    [int]$DaysBack = 7,

    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string[]]$Logs = @("System", "Application"),

    [Parameter()]
    [ValidateSet("Critical", "Error", "Warning", "Information", "Verbose")]
    [string[]]$Levels = @("Critical", "Error", "Warning"),

    [Parameter()]
    [ValidateRange(1, 200)]
    [int]$Top = 25,

    [Parameter()]
    [ValidateSet("Terminal", "Html", "Both")]
    [string]$Output = "Html",

    [Parameter()]
    [string]$OutputPath,

    [Parameter()]
    [switch]$NoOpen
)

$ErrorActionPreference = "Continue"

$levelMap = @{
    Critical    = 1
    Error       = 2
    Warning     = 3
    Information = 4
    Verbose     = 5
}

function ConvertTo-CompactMessage {
    param([AllowNull()][string]$Message)

    if ([string]::IsNullOrWhiteSpace($Message)) {
        return ""
    }

    return (($Message -replace "\r?\n", " ") -replace "\s+", " ").Trim()
}

function ConvertTo-ShortText {
    param(
        [AllowNull()][string]$Text,
        [int]$MaxLength = 240
    )

    if ([string]::IsNullOrWhiteSpace($Text) -or $Text.Length -le $MaxLength) {
        return $Text
    }

    return "$($Text.Substring(0, $MaxLength - 3))..."
}

function ConvertTo-HtmlSafe {
    param([AllowNull()][object]$Value)

    if ($null -eq $Value) {
        return ""
    }

    return [System.Net.WebUtility]::HtmlEncode([string]$Value)
}

function Get-EventLevelName {
    param([object]$EventRecord)

    if (-not [string]::IsNullOrWhiteSpace($EventRecord.LevelDisplayName)) {
        return $EventRecord.LevelDisplayName
    }

    switch ($EventRecord.Level) {
        1 { "Critical" }
        2 { "Error" }
        3 { "Warning" }
        4 { "Information" }
        5 { "Verbose" }
        default { "Unknown" }
    }
}

function Get-LevelIds {
    param([string[]]$LevelNames)

    foreach ($levelName in $LevelNames) {
        $levelMap[$levelName]
    }
}

function Get-EventLogRecords {
    param(
        [string[]]$LogNames,
        [datetime]$StartTime,
        [int[]]$LevelIds
    )

    $events = @()
    $errors = @()

    foreach ($logName in $LogNames) {
        try {
            $filter = @{
                LogName   = $logName
                StartTime = $StartTime
                Level     = $LevelIds
            }

            $events += Get-WinEvent -FilterHashtable $filter -ErrorAction Stop | ForEach-Object {
                [pscustomobject]@{
                    TimeCreated      = $_.TimeCreated
                    Log              = $logName
                    Id               = $_.Id
                    LevelDisplayName = Get-EventLevelName $_
                    ProviderName     = $_.ProviderName
                    Message          = ConvertTo-CompactMessage $_.Message
                }
            }
        }
        catch {
            $errors += [pscustomobject]@{
                Log     = $logName
                Message = ConvertTo-CompactMessage $_.Exception.Message
            }
        }
    }

    [pscustomobject]@{
        Events = @($events | Sort-Object TimeCreated -Descending)
        Errors = $errors
    }
}

function Get-RecurringEventGroups {
    param([object[]]$Events)

    $groups = foreach ($group in ($Events | Group-Object Log, ProviderName, Id, LevelDisplayName)) {
        $items = @($group.Group | Sort-Object TimeCreated -Descending)
        $latest = $items | Select-Object -First 1
        $first = $items | Select-Object -Last 1

        [pscustomobject]@{
            Count            = $group.Count
            Latest           = $latest.TimeCreated
            First            = $first.TimeCreated
            Log              = $latest.Log
            ProviderName     = $latest.ProviderName
            Id               = $latest.Id
            LevelDisplayName = $latest.LevelDisplayName
            ExampleMessage   = $latest.Message
        }
    }

    @($groups | Sort-Object Count, Latest -Descending | Select-Object -First $Top)
}

function Get-LevelCounts {
    param([object[]]$Events)

    $Events |
        Group-Object LevelDisplayName |
        Sort-Object Count -Descending |
        ForEach-Object {
            [pscustomobject]@{
                Level = $_.Name
                Count = $_.Count
            }
        }
}

function Write-TerminalReport {
    param(
        [object]$Report,
        [object[]]$RecurringEvents,
        [object[]]$LevelCounts,
        [object[]]$RecentEvents,
        [object[]]$CollectionErrors
    )

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Windows Event Log Analysis" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Computer : $($Report.ComputerName)"
    Write-Host "Window   : $($Report.StartTime) -> $($Report.EndTime)"
    Write-Host "Logs     : $($Report.Logs -join ', ')"
    Write-Host "Levels   : $($Report.Levels -join ', ')"
    Write-Host "Events   : $($Report.TotalEvents)"
    Write-Host ""

    if ($CollectionErrors.Count -gt 0) {
        Write-Host "Collection warnings:" -ForegroundColor Yellow
        $CollectionErrors | Format-Table Log, Message -AutoSize -Wrap
    }

    Write-Host "Events by level:" -ForegroundColor Cyan
    if ($LevelCounts.Count -eq 0) {
        Write-Host "  No matching events found."
    }
    else {
        $LevelCounts | Format-Table Level, Count -AutoSize
    }

    Write-Host ""
    Write-Host "Top recurring events:" -ForegroundColor Cyan
    if ($RecurringEvents.Count -eq 0) {
        Write-Host "  No recurring events found."
    }
    else {
        foreach ($eventGroup in $RecurringEvents) {
            Write-Host ("  [{0}x] {1} {2} {3} #{4} - {5}" -f $eventGroup.Count, $eventGroup.Latest, $eventGroup.Log, $eventGroup.LevelDisplayName, $eventGroup.Id, $eventGroup.ProviderName) -ForegroundColor White
            Write-Host ("       First seen: {0}" -f $eventGroup.First) -ForegroundColor DarkGray
            if (-not [string]::IsNullOrWhiteSpace($eventGroup.ExampleMessage)) {
                Write-Host ("       Example: {0}" -f (ConvertTo-ShortText $eventGroup.ExampleMessage)) -ForegroundColor Gray
            }
        }
    }

    Write-Host ""
    Write-Host "Recent critical/error events:" -ForegroundColor Cyan
    if ($RecentEvents.Count -eq 0) {
        Write-Host "  No recent critical/error events found."
    }
    else {
        foreach ($recentEvent in $RecentEvents) {
            Write-Host ("  {0} {1} {2} #{3} - {4}" -f $recentEvent.TimeCreated, $recentEvent.Log, $recentEvent.LevelDisplayName, $recentEvent.Id, $recentEvent.ProviderName) -ForegroundColor White
            if (-not [string]::IsNullOrWhiteSpace($recentEvent.Message)) {
                Write-Host ("       {0}" -f (ConvertTo-ShortText $recentEvent.Message)) -ForegroundColor Gray
            }
        }
    }
}

function New-HtmlReport {
    param(
        [object]$Report,
        [object[]]$RecurringEvents,
        [object[]]$LevelCounts,
        [object[]]$RecentEvents,
        [object[]]$CollectionErrors
    )

    $generatedAt = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

    $logOptions = ($Report.Logs | Sort-Object -Unique | ForEach-Object {
        "<option value=""$((ConvertTo-HtmlSafe $_))"">$((ConvertTo-HtmlSafe $_))</option>"
    }) -join "`n"

    $levelOptions = ($Report.Levels | Sort-Object -Unique | ForEach-Object {
        "<option value=""$((ConvertTo-HtmlSafe $_))"">$((ConvertTo-HtmlSafe $_))</option>"
    }) -join "`n"

    $levelCards = if ($LevelCounts.Count -gt 0) {
        ($LevelCounts | ForEach-Object {
            "<div class=""card""><span>$((ConvertTo-HtmlSafe $_.Level))</span><strong>$((ConvertTo-HtmlSafe $_.Count))</strong></div>"
        }) -join "`n"
    }
    else {
        "<div class=""empty"">No matching events found.</div>"
    }

    $collectionWarningRows = if ($CollectionErrors.Count -gt 0) {
        ($CollectionErrors | ForEach-Object {
            "<tr><td>$((ConvertTo-HtmlSafe $_.Log))</td><td>$((ConvertTo-HtmlSafe $_.Message))</td></tr>"
        }) -join "`n"
    }
    else {
        "<tr><td colspan=""2"" class=""muted"">No collection warnings.</td></tr>"
    }

    $recurringRows = if ($RecurringEvents.Count -gt 0) {
        ($RecurringEvents | ForEach-Object {
            @"
<tr data-log="$((ConvertTo-HtmlSafe $_.Log))" data-level="$((ConvertTo-HtmlSafe $_.LevelDisplayName))">
  <td class="count">$((ConvertTo-HtmlSafe $_.Count))</td>
  <td>$((ConvertTo-HtmlSafe $_.Latest))</td>
  <td>$((ConvertTo-HtmlSafe $_.First))</td>
  <td>$((ConvertTo-HtmlSafe $_.Log))</td>
  <td><span class="pill $((ConvertTo-HtmlSafe $_.LevelDisplayName).ToLowerInvariant())">$((ConvertTo-HtmlSafe $_.LevelDisplayName))</span></td>
  <td>$((ConvertTo-HtmlSafe $_.Id))</td>
  <td>$((ConvertTo-HtmlSafe $_.ProviderName))</td>
  <td class="message">$((ConvertTo-HtmlSafe $_.ExampleMessage))</td>
</tr>
"@
        }) -join "`n"
    }
    else {
        "<tr><td colspan=""8"" class=""muted"">No recurring events found.</td></tr>"
    }

    $recentRows = if ($RecentEvents.Count -gt 0) {
        ($RecentEvents | ForEach-Object {
            @"
<tr data-log="$((ConvertTo-HtmlSafe $_.Log))" data-level="$((ConvertTo-HtmlSafe $_.LevelDisplayName))">
  <td>$((ConvertTo-HtmlSafe $_.TimeCreated))</td>
  <td>$((ConvertTo-HtmlSafe $_.Log))</td>
  <td><span class="pill $((ConvertTo-HtmlSafe $_.LevelDisplayName).ToLowerInvariant())">$((ConvertTo-HtmlSafe $_.LevelDisplayName))</span></td>
  <td>$((ConvertTo-HtmlSafe $_.Id))</td>
  <td>$((ConvertTo-HtmlSafe $_.ProviderName))</td>
  <td class="message">$((ConvertTo-HtmlSafe $_.Message))</td>
</tr>
"@
        }) -join "`n"
    }
    else {
        "<tr><td colspan=""6"" class=""muted"">No recent critical/error events found.</td></tr>"
    }

@"
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Windows Event Log Analysis</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0d1117;
      --panel: #151b23;
      --panel-2: #1f2937;
      --text: #e5edf6;
      --muted: #95a3b8;
      --accent: #67e8f9;
      --border: #303b4d;
      --critical: #fb7185;
      --error: #f97316;
      --warning: #facc15;
      --info: #60a5fa;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: radial-gradient(circle at top left, #172554 0, var(--bg) 38rem);
      color: var(--text);
      font-family: "Segoe UI", Arial, sans-serif;
      line-height: 1.45;
    }
    main { max-width: 1440px; margin: 0 auto; padding: 32px; }
    header { margin-bottom: 28px; }
    h1 { margin: 0 0 8px; font-size: 2.2rem; letter-spacing: -0.04em; }
    h2 { margin: 28px 0 12px; font-size: 1.25rem; }
    .muted, .empty { color: var(--muted); }
    .meta, .cards { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
    .card, .panel {
      background: rgba(21, 27, 35, 0.88);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.2);
    }
    .card { padding: 16px; }
    .card span { display: block; color: var(--muted); font-size: 0.86rem; }
    .card strong { display: block; margin-top: 8px; font-size: 1.45rem; color: var(--accent); }
    .panel { overflow: hidden; }
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: -4px 0 12px;
    }
    .controls input, .controls select {
      min-width: 180px;
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
    .table-status {
      align-self: center;
      color: var(--muted);
      font-size: 0.9rem;
    }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; min-width: 920px; }
    th, td { padding: 11px 12px; border-bottom: 1px solid var(--border); vertical-align: top; text-align: left; }
    th { color: var(--muted); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.08em; background: rgba(31, 41, 55, 0.8); }
    th[data-sort] { cursor: pointer; user-select: none; }
    th[data-sort]::after { content: " ↕"; color: var(--muted); font-weight: 400; }
    th.sort-asc::after { content: " ↑"; color: var(--accent); }
    th.sort-desc::after { content: " ↓"; color: var(--accent); }
    tr:hover td { background: rgba(103, 232, 249, 0.04); }
    tr.is-hidden { display: none; }
    .count { color: var(--accent); font-weight: 700; }
    .message { min-width: 360px; max-width: 720px; }
    .pill {
      display: inline-block;
      padding: 3px 9px;
      border-radius: 999px;
      border: 1px solid currentColor;
      font-size: 0.78rem;
      font-weight: 700;
    }
    .critical { color: var(--critical); }
    .error { color: var(--error); }
    .warning { color: var(--warning); }
    .information, .verbose { color: var(--info); }
    footer { margin-top: 28px; color: var(--muted); font-size: 0.9rem; }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Windows Event Log Analysis</h1>
      <div class="muted">Generated $((ConvertTo-HtmlSafe $generatedAt)) on $((ConvertTo-HtmlSafe $Report.ComputerName))</div>
    </header>

    <section class="meta">
      <div class="card"><span>Time window</span><strong>$((ConvertTo-HtmlSafe $Report.DaysBack)) day(s)</strong></div>
      <div class="card"><span>Total events</span><strong>$((ConvertTo-HtmlSafe $Report.TotalEvents))</strong></div>
      <div class="card"><span>Logs</span><strong>$((ConvertTo-HtmlSafe ($Report.Logs -join ", ")))</strong></div>
      <div class="card"><span>Levels</span><strong>$((ConvertTo-HtmlSafe ($Report.Levels -join ", ")))</strong></div>
    </section>

    <h2>Events by Level</h2>
    <section class="cards">
      $levelCards
    </section>

    <h2>Top Recurring Events</h2>
    <div class="controls" data-controls-for="recurring-events">
      <input type="search" placeholder="Filter recurring events..." data-filter-text aria-label="Filter recurring events">
      <select data-filter-log aria-label="Filter recurring events by log">
        <option value="">All logs</option>
        $logOptions
      </select>
      <select data-filter-level aria-label="Filter recurring events by level">
        <option value="">All levels</option>
        $levelOptions
      </select>
      <span class="table-status" data-table-status></span>
    </div>
    <section class="panel table-wrap">
      <table id="recurring-events" class="interactive-table">
        <thead>
          <tr><th data-sort="number">Count</th><th data-sort="date">Latest</th><th data-sort="date">First</th><th data-sort="text">Log</th><th data-sort="text">Level</th><th data-sort="number">ID</th><th data-sort="text">Provider</th><th data-sort="text">Example message</th></tr>
        </thead>
        <tbody>
          $recurringRows
        </tbody>
      </table>
    </section>

    <h2>Recent Critical/Error Events</h2>
    <div class="controls" data-controls-for="recent-events">
      <input type="search" placeholder="Filter recent events..." data-filter-text aria-label="Filter recent events">
      <select data-filter-log aria-label="Filter recent events by log">
        <option value="">All logs</option>
        $logOptions
      </select>
      <select data-filter-level aria-label="Filter recent events by level">
        <option value="">All levels</option>
        $levelOptions
      </select>
      <span class="table-status" data-table-status></span>
    </div>
    <section class="panel table-wrap">
      <table id="recent-events" class="interactive-table">
        <thead>
          <tr><th data-sort="date">Time</th><th data-sort="text">Log</th><th data-sort="text">Level</th><th data-sort="number">ID</th><th data-sort="text">Provider</th><th data-sort="text">Message</th></tr>
        </thead>
        <tbody>
          $recentRows
        </tbody>
      </table>
    </section>

    <h2>Collection Warnings</h2>
    <section class="panel table-wrap">
      <table>
        <thead>
          <tr><th>Log</th><th>Message</th></tr>
        </thead>
        <tbody>
          $collectionWarningRows
        </tbody>
      </table>
    </section>

    <footer>
      Window: $((ConvertTo-HtmlSafe $Report.StartTime)) to $((ConvertTo-HtmlSafe $Report.EndTime)).
      Generated by Analyze-EventLogs.ps1.
    </footer>
  </main>
  <script>
    function getCellValue(row, columnIndex, sortType) {
      const cell = row.cells[columnIndex];
      const value = cell ? cell.textContent.trim() : "";

      if (sortType === "number") {
        const parsedNumber = Number(value.replace(/[^0-9.-]/g, ""));
        return Number.isNaN(parsedNumber) ? 0 : parsedNumber;
      }

      if (sortType === "date") {
        const parsedDate = Date.parse(value);
        return Number.isNaN(parsedDate) ? 0 : parsedDate;
      }

      return value.toLowerCase();
    }

    function applyTableFilters(table, controls) {
      const textFilter = (controls.querySelector("[data-filter-text]")?.value || "").toLowerCase();
      const logFilter = controls.querySelector("[data-filter-log]")?.value || "";
      const levelFilter = controls.querySelector("[data-filter-level]")?.value || "";
      const rows = Array.from(table.tBodies[0].rows);
      let visibleCount = 0;

      rows.forEach(function(row) {
        const rowText = row.textContent.toLowerCase();
        const rowLog = row.dataset.log || "";
        const rowLevel = row.dataset.level || "";
        const isMatch =
          (!textFilter || rowText.includes(textFilter)) &&
          (!logFilter || rowLog === logFilter) &&
          (!levelFilter || rowLevel === levelFilter);

        row.classList.toggle("is-hidden", !isMatch);
        if (isMatch) {
          visibleCount += 1;
        }
      });

      const status = controls.querySelector("[data-table-status]");
      if (status) {
        status.textContent = visibleCount + " of " + rows.length + " shown";
      }
    }

    function sortTable(table, header, columnIndex) {
      const sortType = header.dataset.sort || "text";
      const nextDirection = header.classList.contains("sort-asc") ? "desc" : "asc";
      const rows = Array.from(table.tBodies[0].rows);

      table.querySelectorAll("th[data-sort]").forEach(function(sortHeader) {
        sortHeader.classList.remove("sort-asc", "sort-desc");
      });
      header.classList.add(nextDirection === "asc" ? "sort-asc" : "sort-desc");

      rows.sort(function(left, right) {
        const leftValue = getCellValue(left, columnIndex, sortType);
        const rightValue = getCellValue(right, columnIndex, sortType);

        if (leftValue < rightValue) {
          return nextDirection === "asc" ? -1 : 1;
        }
        if (leftValue > rightValue) {
          return nextDirection === "asc" ? 1 : -1;
        }
        return 0;
      });

      rows.forEach(function(row) {
        table.tBodies[0].appendChild(row);
      });
    }

    document.querySelectorAll(".interactive-table").forEach(function(table) {
      const controls = document.querySelector('[data-controls-for="' + table.id + '"]');
      if (controls) {
        controls.querySelectorAll("input, select").forEach(function(control) {
          control.addEventListener("input", function() { applyTableFilters(table, controls); });
          control.addEventListener("change", function() { applyTableFilters(table, controls); });
        });
        applyTableFilters(table, controls);
      }

      table.querySelectorAll("th[data-sort]").forEach(function(header, columnIndex) {
        header.addEventListener("click", function() { sortTable(table, header, columnIndex); });
      });
    });
  </script>
</body>
</html>
"@
}

$startTime = (Get-Date).AddDays(-$DaysBack)
$endTime = Get-Date
$levelIds = @(Get-LevelIds $Levels)

$result = Get-EventLogRecords -LogNames $Logs -StartTime $startTime -LevelIds $levelIds
$events = @($result.Events)
$collectionErrors = @($result.Errors)
$recurringEvents = @(Get-RecurringEventGroups -Events $events)
$levelCounts = @(Get-LevelCounts -Events $events)
$recentEvents = @(
    $events |
        Where-Object { $_.LevelDisplayName -in @("Critical", "Error") } |
        Sort-Object TimeCreated -Descending |
        Select-Object -First $Top
)

$report = [pscustomobject]@{
    ComputerName = $env:COMPUTERNAME
    DaysBack     = $DaysBack
    StartTime    = $startTime
    EndTime      = $endTime
    Logs         = $Logs
    Levels       = $Levels
    TotalEvents  = $events.Count
}

if ($Output -in @("Terminal", "Both")) {
    Write-TerminalReport -Report $report -RecurringEvents $recurringEvents -LevelCounts $levelCounts -RecentEvents $recentEvents -CollectionErrors $collectionErrors
}

if ($Output -in @("Html", "Both")) {
    if ([string]::IsNullOrWhiteSpace($OutputPath)) {
        $fileName = "EventLogReport_{0}.html" -f (Get-Date -Format "yyyyMMdd_HHmmss")
        $OutputPath = Join-Path ([System.IO.Path]::GetTempPath()) $fileName
    }

    $html = New-HtmlReport -Report $report -RecurringEvents $recurringEvents -LevelCounts $levelCounts -RecentEvents $recentEvents -CollectionErrors $collectionErrors
    $resolvedOutputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputPath)
    $html | Out-File -FilePath $resolvedOutputPath -Encoding UTF8
    Write-Host "HTML report written to: $resolvedOutputPath" -ForegroundColor Green

    if (-not $NoOpen) {
        try {
            Invoke-Item -LiteralPath $resolvedOutputPath
        }
        catch {
            Write-Warning "Could not open HTML report automatically: $($_.Exception.Message)"
        }
    }
}
