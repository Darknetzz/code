####################################################################
#   Scripted by Kristian Røste 2026-01-06
#
#   Info:
#   this script kills the processes, keeping
#   license alive. Normal runtime 1-2 hours. This kills
#   processes over the configured threshold ($hours hours; default 6).
#
####################################################################

param(
    [switch]$DryRun
)

## Checking if processes older than $hours hours
# One or more process name prefixes (wildcards: each entry matches "Prefix*")
$application = @("APPLICATION_NAME")  # string or array, e.g. @('App1', 'App2')
$hours       = 6
$now         = Get-Date

$appPrefixes = @($application)
$processes = foreach ($prefix in $appPrefixes) {
    if ([string]::IsNullOrWhiteSpace($prefix)) { continue }
    Get-Process -Name "$prefix*" -ErrorAction SilentlyContinue
}
$processes = @($processes | Sort-Object -Property Id -Unique)

$processesc = if ($processes.Count) { $processes.Count } else { "0" }
$kill       = $processes | Where-Object { $_.StartTime -lt $now.AddHours(-$hours) }
$killList   = @($kill)
$killc      = if ($killList.Count) { $killList.Count } else { "0" }

$debug  = $False
$logdir = (Get-Location).Path # "C:\Script"
$logfile = (Get-Item $PSCommandPath).BaseName + ".log"
$logpath = Join-Path $logdir $logfile

## Defines the logfile and creates it if doesn't exist.
if (!(Test-Path -LiteralPath $logpath)) {
    New-Item -Path $logpath -ItemType File | Out-Null
}

function Write-Log($text) {
    Add-Content -Path $logpath -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $text"
}

if ($debug -eq $True) {
    Write-Log "Found $killc processes running more than $hours hours. ($processesc total)"
}

## Does nothing if no processes found
if ($killList.Count -eq 0) {
    if ($debug -eq $True) {
        Write-Log "No process to kill."
    }
    exit 0
}

$exitCode = 0
foreach ($p in $killList) {
    $detail = "$($p.Name) (Id=$($p.Id), StartTime=$($p.StartTime))"
    try {
        if ($DryRun) {
            Write-Log "DryRun: would stop $detail"
        }
        else {
            Stop-Process -InputObject $p -Force -ErrorAction Stop
            Write-Log "Stopped $detail"
        }
    }
    catch {
        Write-Log "Failed to stop $detail : $_"
        $exitCode = 1
    }
}

exit $exitCode
