####################################################################
#   Scripted by Kristian Røste 2026-01-06
#   
#
#   Info: 
#   this script kills the processes, keeping
#   license alive. Normal runtime 1-2 hours. This kills
#   prosesses over 12 hours runtime.
#
####################################################################

## Checking if processes older than $hours hours
$application = "APPLICATION_NAME"  # Change to your application name
$hours       = 6
$now         = Get-Date
$processes   = Get-Process "$application*"
$processesc  = $(if ($processes.Count) { $processes.Count } else { "0" })
$kill        = $processes | Where-Object StartTime -lt ($now).AddHours(-$hours)
$killc       = $(if ($kill.Count) { $kill.Count } else { "0" })
$debug       = $False
$logdir      = (Get-Location).Path # "C:\Script"
$logfile     = (Get-Item $PSCommandPath).BaseName + ".log"
$logpath     = Join-Path $logdir $logfile

## Defines the logfile and creates it if doesn't exist.
if (!(Test-Path $logpath)) {
   New-Item -path "$logdir" -name "$logfile" -type "file"
}

function Write-Log($text) {
    "[$now] $text" >> $logfile
}

if ($debug -eq $True) {
    Write-Log "Found $killc processes running more than $hours hours. ($processesc total)"
}

## Does nothing if no processes found
if ($null -eq $kill) {
    if ($debug -eq $True) {
        Write-Log "No process to kill."
    }
    Exit 0
}
else {
    ## Stops the process and writes date to logfile
    $kill | Stop-Process -Force
    Write-Log "Hanging process stopped"
}