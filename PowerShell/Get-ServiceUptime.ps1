# Show uptime for Windows services by process start time.
# Matches against service Name or DisplayName; wildcards supported.
# Usage: .\Get-ServiceUptime.ps1 Spooler
#        .\Get-ServiceUptime.ps1 -Name 'wuauserv'
#        .\Get-ServiceUptime.ps1 'SQL*'
#        .\Get-ServiceUptime.ps1 '*Print*'

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [SupportsWildcards()]
    [string] $Name
)

$services = @(Get-CimInstance -ClassName Win32_Service | Where-Object {
    $_.Name -like $Name -or $_.DisplayName -like $Name
})

if ($services.Count -eq 0) {
    Write-Warning "No services matched '$Name'."
    return
}

foreach ($service in $services) {
    if ($service.ProcessId -le 0) {
        Write-Warning "Service '$($service.Name)' is not running."
        continue
    }

    $proc = Get-Process -Id $service.ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) {
        Write-Warning "Service '$($service.Name)' reports PID $($service.ProcessId) but the process was not found."
        continue
    }

    [PSCustomObject]@{
        ServiceName = $service.Name
        DisplayName = $service.DisplayName
        PID         = $service.ProcessId
        StartTime   = $proc.StartTime
        Uptime      = (Get-Date) - $proc.StartTime
    }
}
