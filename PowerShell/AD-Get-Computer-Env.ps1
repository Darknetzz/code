<#
.SYNOPSIS
    Environment Variable Inspector

.DESCRIPTION
    View environment variables locally or remotely using:
    - Local
    - PowerShell Remoting
    - Remote Registry
    - CIM/WMI

    Supports:
    - Wildcard filtering
    - Machine/User variables
    - CSV export
#>

function Show-Results {
    param($Results)

    if (-not $Results) {
        Write-Host "`nNo results found." -ForegroundColor Yellow
        return
    }

    $Results |
        Sort-Object Scope, Name |
        Format-Table Scope, Name, Value -AutoSize -Wrap
}

function Get-LocalEnvVars {

    [System.Environment]::GetEnvironmentVariables("Machine").GetEnumerator() |
        ForEach-Object {
            [PSCustomObject]@{
                Scope = "Machine"
                Name  = $_.Key
                Value = $_.Value
            }
        }

    [System.Environment]::GetEnvironmentVariables("User").GetEnumerator() |
        ForEach-Object {
            [PSCustomObject]@{
                Scope = "User"
                Name  = $_.Key
                Value = $_.Value
            }
        }
}

function Get-RemoteEnvVarsPSRemoting {
    param([string]$ComputerName)

    Invoke-Command -ComputerName $ComputerName -ScriptBlock {

        [System.Environment]::GetEnvironmentVariables("Machine").GetEnumerator() |
            ForEach-Object {
                [PSCustomObject]@{
                    Scope = "Machine"
                    Name  = $_.Key
                    Value = $_.Value
                }
            }

        [System.Environment]::GetEnvironmentVariables("User").GetEnumerator() |
            ForEach-Object {
                [PSCustomObject]@{
                    Scope = "User"
                    Name  = $_.Key
                    Value = $_.Value
                }
            }
    }
}

function Get-RemoteEnvVarsRegistry {
    param([string]$ComputerName)

    $path = "\\$ComputerName\HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment"

    reg query $path 2>$null |
        Select-Object -Skip 1 |
        ForEach-Object {

            if ($_ -match '^\s+(\S+)\s+REG_\S+\s+(.+)$') {
                [PSCustomObject]@{
                    Scope = "Machine"
                    Name  = $Matches[1]
                    Value = $Matches[2]
                }
            }
        }
}

function Get-RemoteEnvVarsCIM {
    param([string]$ComputerName)

    Get-CimInstance Win32_Environment -ComputerName $ComputerName |
        ForEach-Object {

            [PSCustomObject]@{
                Scope = if ($_.UserName) { "User" } else { "Machine" }
                Name  = $_.Name
                Value = $_.VariableValue
            }
        }
}

# Main Menu

do {

    Clear-Host

    Write-Host "========================================"
    Write-Host " Environment Variable Inspector"
    Write-Host "========================================"
    Write-Host ""
    Write-Host "1. Local Computer"
    Write-Host "2. Remote Computer (PowerShell Remoting)"
    Write-Host "3. Remote Computer (Remote Registry)"
    Write-Host "4. Remote Computer (CIM/WMI)"
    Write-Host "5. Exit"
    Write-Host ""

    $choice = Read-Host "Select option"

    switch ($choice) {

        "1" {
            $results = Get-LocalEnvVars
        }

        "2" {
            $computer = Read-Host "Computer Name"
            $results = Get-RemoteEnvVarsPSRemoting -ComputerName $computer
        }

        "3" {
            $computer = Read-Host "Computer Name"
            $results = Get-RemoteEnvVarsRegistry -ComputerName $computer
        }

        "4" {
            $computer = Read-Host "Computer Name"
            $results = Get-RemoteEnvVarsCIM -ComputerName $computer
        }

        "5" {
            break
        }

        default {
            continue
        }
    }

    if ($choice -ne "5") {

        $filter = Read-Host "Variable name filter (* for all)"

        if ($filter -and $filter -ne "*") {
            $results = $results | Where-Object Name -like $filter
        }

        Write-Host ""
        Write-Host "1. Show All"
        Write-Host "2. Machine Variables Only"
        Write-Host "3. User Variables Only"
        Write-Host ""

        $scopeChoice = Read-Host "Select"

        switch ($scopeChoice) {
            "2" { $results = $results | Where-Object Scope -eq "Machine" }
            "3" { $results = $results | Where-Object Scope -eq "User" }
        }

        Show-Results $results

        Write-Host ""
        $export = Read-Host "Export to CSV? (Y/N)"

        if ($export -match "^Y") {

            $csv = Join-Path $env:TEMP "EnvironmentVariables.csv"

            $results |
                Export-Csv $csv -NoTypeInformation

            Write-Host ""
            Write-Host "Exported to $csv" -ForegroundColor Green
        }

        Pause
    }

} while ($true)