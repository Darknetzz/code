####################################################################
#   Scripted by Kristian Røste 2026-01-06
#
#   Info:
#   this script kills the processes, keeping
#   license alive. Normal runtime 1-2 hours. This kills
#   processes over the configured threshold ($thresholdHours hours; default 6).
#
#   Optional parameters (-Application, -Hours, -LogDir, -DebugLogging, -DryRun)
#   override the script defaults below when you pass them.
#
####################################################################

param(
    [Parameter()]
    [string[]]$Application,

    [Parameter()]
    [int]$Hours,

    [Parameter()]
    [string]$LogDir,

    [switch]$DryRun,

    [Parameter()]
    [switch]$DebugLogging
)

## Defaults (edit here). Parameters above override when supplied on the command line.
# One or more process name prefixes (wildcards: each entry matches "Prefix*").
# Name must differ from parameter $Application (PowerShell variables are case-insensitive).
$processNamePrefixes = @("APPLICATION_NAME")  # string or array, e.g. @('App1', 'App2')
$thresholdHours = 6
$debug       = $False
$resolvedLogDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

if ($PSBoundParameters.ContainsKey('Application')) {
    $processNamePrefixes = @($Application)
}
if ($PSBoundParameters.ContainsKey('Hours')) {
    if ($Hours -lt 1) {
        throw "Parameter 'Hours' must be at least 1. Got: $Hours"
    }
    $thresholdHours = $Hours
}
if ($PSBoundParameters.ContainsKey('LogDir')) {
    if ([string]::IsNullOrWhiteSpace($LogDir)) {
        throw "Parameter 'LogDir' cannot be empty."
    }
    $resolvedLogDir = $LogDir
}
if ($PSBoundParameters.ContainsKey('DebugLogging')) {
    $debug = [bool]$DebugLogging
}

## Checking if processes older than $thresholdHours hours
$now = Get-Date

$processes = foreach ($prefix in @($processNamePrefixes)) {
    if ([string]::IsNullOrWhiteSpace($prefix)) { continue }
    Get-Process -Name "$prefix*" -ErrorAction SilentlyContinue
}
$processes = @($processes | Sort-Object -Property Id -Unique)

$processesc = if ($processes.Count) { $processes.Count } else { "0" }
$kill       = $processes | Where-Object { $_.StartTime -lt $now.AddHours(-$thresholdHours) }
$killList   = @($kill)
$killc      = if ($killList.Count) { $killList.Count } else { "0" }

$logfile = (Get-Item $PSCommandPath).BaseName + ".log"
$logpath = Join-Path $resolvedLogDir $logfile

## Defines the logfile and creates it if doesn't exist.
if (!(Test-Path -LiteralPath $logpath)) {
    New-Item -Path $logpath -ItemType File | Out-Null
}

function Write-Log($text) {
    Add-Content -Path $logpath -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $text"
}

if ($debug -eq $True) {
    Write-Log "Found $killc processes running more than $thresholdHours hours. ($processesc total)"
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
