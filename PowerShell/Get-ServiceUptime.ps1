<#
.SYNOPSIS
Show uptime for Windows services by process start time or SCM event 7036.

.DESCRIPTION
Matches against service Name or DisplayName; wildcards are supported.

Shared-process services (e.g. svchost) default to Event Log 7036 for true
service start; own-process services use Win32_Process CreationDate.
Falls back to process time when no matching 7036 event is found.

.PARAMETER Name
Service name or display name. Wildcards (*, ?) are supported.

.PARAMETER Source
How to resolve start time: Auto (default), EventLog, or Process.

.PARAMETER Short
Format Uptime as shorthand (e.g. "2d 7h 12m") instead of
"2 days, 7 hours, 12 minutes".

.EXAMPLE
.\Get-ServiceUptime.ps1 Spooler

.EXAMPLE
.\Get-ServiceUptime.ps1 'SQL*'

.EXAMPLE
.\Get-ServiceUptime.ps1 '*Print*' -Source EventLog

.EXAMPLE
.\Get-ServiceUptime.ps1 wuauserv -Source Process -Short
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [SupportsWildcards()]
    [string] $Name,

    [Parameter()]
    [ValidateSet('Auto', 'EventLog', 'Process')]
    [string] $Source = 'Auto',

    [Parameter()]
    [switch] $Short
)

function Format-RelativeUptime {
    param(
        [Parameter(Mandatory)] [TimeSpan] $Uptime,
        [switch] $Short
    )

    $units = @(
        @{ Value = $Uptime.Days;    Short = 'd'; Singular = 'day';    Plural = 'days' }
        @{ Value = $Uptime.Hours;   Short = 'h'; Singular = 'hour';   Plural = 'hours' }
        @{ Value = $Uptime.Minutes; Short = 'm'; Singular = 'minute'; Plural = 'minutes' }
    )

    $parts = foreach ($unit in $units) {
        if ($unit.Value -le 0) { continue }
        if ($Short) {
            "$($unit.Value)$($unit.Short)"
        }
        else {
            $label = if ($unit.Value -eq 1) { $unit.Singular } else { $unit.Plural }
            "$($unit.Value) $label"
        }
    }

    if (@($parts).Count -gt 0) {
        return $(if ($Short) { $parts -join ' ' } else { $parts -join ', ' })
    }

    $seconds = [Math]::Max(0, [int][Math]::Floor($Uptime.TotalSeconds))
    if ($Short) { return "${seconds}s" }
    $label = if ($seconds -eq 1) { 'second' } else { 'seconds' }
    return "$seconds $label"
}

function Test-SharedServiceProcess {
    param([Parameter(Mandatory)] $Service)
    return $Service.ServiceType -match 'Share Process'
}

function Get-ServiceProcessStartTime {
    param([Parameter(Mandatory)] $Service)

    if ($Service.ProcessId -le 0) {
        return $null
    }

    # Win32_Process.CreationDate works without elevation; Get-Process StartTime often does not.
    $proc = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$($Service.ProcessId)" -ErrorAction SilentlyContinue
    return $proc.CreationDate
}

function Test-ServiceEnteredRunningEvent {
    param([Parameter(Mandatory)] $Event)

    if ($Event.Properties.Count -lt 2) {
        return $false
    }

    $state = $Event.Properties[1].Value
    if ($state -and $state -match '^(?i)running$') {
        return $true
    }

    return [bool]($Event.Message -match '(?i)entered the running state')
}

function Test-ServiceEventNameMatch {
    param(
        [Parameter(Mandatory)] $Event,
        [Parameter(Mandatory)] [string] $ServiceName,
        [Parameter(Mandatory)] [string] $DisplayName
    )

    if ($Event.Properties.Count -lt 1) {
        return $false
    }

    $loggedName = $Event.Properties[0].Value
    return $loggedName -eq $DisplayName -or $loggedName -eq $ServiceName
}

function Get-ServiceEventLogStartTime {
    param(
        [Parameter(Mandatory)] [string] $ServiceName,
        [Parameter(Mandatory)] [string] $DisplayName
    )

    # Prefer XPath scoped to DisplayName (7036 param1 is usually the display name).
    $candidates = @()
    foreach ($label in @($DisplayName, $ServiceName) | Select-Object -Unique) {
        if ([string]::IsNullOrWhiteSpace($label)) { continue }
        $escaped = $label.Replace("'", "&apos;")
        $xpath = @"
*[System[Provider[@Name='Service Control Manager'] and (EventID=7036)]
  and EventData[Data[@Name='param1']='$escaped']]
"@
        try {
            $candidates = @(Get-WinEvent -LogName System -FilterXPath $xpath -ErrorAction Stop)
            if ($candidates.Count -gt 0) { break }
        }
        catch {
            # No events for this label — try next / fall through
        }
    }

    # Broader scan if XPath found nothing (param naming / older logs)
    if ($candidates.Count -eq 0) {
        try {
            $candidates = @(
                Get-WinEvent -FilterHashtable @{
                    LogName      = 'System'
                    ProviderName = 'Service Control Manager'
                    Id           = 7036
                } -ErrorAction Stop |
                    Where-Object {
                        Test-ServiceEventNameMatch -Event $_ -ServiceName $ServiceName -DisplayName $DisplayName
                    }
            )
        }
        catch {
            return $null
        }
    }

    foreach ($event in $candidates) {
        if (Test-ServiceEnteredRunningEvent -Event $event) {
            return $event.TimeCreated
        }
    }

    return $null
}

function Resolve-ServiceStartTime {
    param(
        [Parameter(Mandatory)] $Service,
        [Parameter(Mandatory)]
        [ValidateSet('Auto', 'EventLog', 'Process')]
        [string] $SourceMode
    )

    $isShared = Test-SharedServiceProcess -Service $Service
    $useEventLog = switch ($SourceMode) {
        'EventLog' { $true }
        'Process'  { $false }
        'Auto'     { $isShared }
    }

    if ($useEventLog) {
        $eventStart = Get-ServiceEventLogStartTime -ServiceName $Service.Name -DisplayName $Service.DisplayName
        if ($eventStart) {
            return [PSCustomObject]@{
                StartTime = $eventStart
                Source    = 'EventLog'
            }
        }

        Write-Warning "No SCM 7036 'running' event for '$($Service.DisplayName)'; falling back to process start time."
    }

    $procStart = Get-ServiceProcessStartTime -Service $Service
    if ($procStart) {
        return [PSCustomObject]@{
            StartTime = $procStart
            Source    = 'Process'
        }
    }

    return $null
}

$services = @(Get-CimInstance -ClassName Win32_Service | Where-Object {
    $_.Name -like $Name -or $_.DisplayName -like $Name
})

if ($services.Count -eq 0) {
    Write-Warning "No services matched '$Name'."
    return
}

$now = Get-Date

foreach ($service in $services) {
    if ($service.ProcessId -le 0) {
        Write-Warning "Service '$($service.Name)' is not running."
        continue
    }

    $resolved = Resolve-ServiceStartTime -Service $service -SourceMode $Source
    if (-not $resolved) {
        Write-Warning "Service '$($service.Name)' reports PID $($service.ProcessId) but start time could not be determined."
        continue
    }

    [PSCustomObject]@{
        ServiceName = $service.Name
        DisplayName = $service.DisplayName
        PID         = $service.ProcessId
        StartTime   = $resolved.StartTime
        Uptime      = Format-RelativeUptime -Uptime ($now - $resolved.StartTime) -Short:$Short
        Source      = $resolved.Source
    }
}
