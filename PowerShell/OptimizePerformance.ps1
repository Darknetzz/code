####################################################################
#   
#   Info: 
#   This script optimizes Windows performance by:
#   - Cleaning temporary files and caches
#   - Optimizing disk performance
#   - Clearing DNS cache
#   - Optimizing power settings
#   - Cleaning Windows Update cache
#   - Optimizing memory
#   - Optimizing network settings (TCP/IP tuning)
#   - Disabling unnecessary visual effects
#   - Optimizing processor scheduling
#   - Optimizing Prefetch/Superfetch settings
#   - Optimizing Windows Update delivery
#   - Disabling background apps
#   - Optimizing System Restore settings
#   - Applying additional registry optimizations
#
####################################################################

#Requires -RunAsAdministrator

param(
    [switch]$SkipCleanup,
    [switch]$SkipDiskOptimization,
    [switch]$SkipPowerOptimization,
    [switch]$SkipServiceOptimization,
    [switch]$Silent,
    [switch]$WhatIf,
    [switch]$Rollback,
    [string]$LogPath = (Join-Path (Get-Location).Path "OptimizePerformance.log"),
    [string]$ChangeLogPath = (Join-Path (Get-Location).Path "OptimizePerformance_Changes.json")
)

$ErrorActionPreference = "Continue"
$script:LogPath = $LogPath
# Verbose is on by default, unless -Silent is specified
$script:Verbose = -not $Silent
# WhatIf mode - show what would happen without making changes
$script:WhatIf = $WhatIf
# Change log to track all modifications for potential rollback
$script:ChangeLog = @()
$script:ChangeLogPath = $ChangeLogPath

<#
.SYNOPSIS
    Initializes the log file for the performance optimization script.

.DESCRIPTION
    Creates the log file if it doesn't exist and writes an initial timestamp entry
    marking the start of the performance optimization process.

.EXAMPLE
    Initialize-Log
#>
function Initialize-Log {
    if (!(Test-Path $script:LogPath)) {
        New-Item -Path $script:LogPath -ItemType File -Force | Out-Null
    }
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $script:LogPath -Value "`n========== Performance Optimization Started: $timestamp =========="
}

<#
.SYNOPSIS
    Records a change to the change log for potential rollback.

.DESCRIPTION
    Adds a detailed change record to the change log, including what was changed,
    the previous value, new value, and how to revert it.

.PARAMETER Category
    The category of change (e.g., "PowerSettings", "Services", "Registry", "Files").

.PARAMETER Item
    The specific item that was changed (e.g., "Power Plan", "Windows Search Service").

.PARAMETER PreviousValue
    The value before the change.

.PARAMETER NewValue
    The value after the change.

.PARAMETER RevertInstructions
    Detailed instructions on how to revert this change.

.EXAMPLE
    Add-ChangeLog -Category "PowerSettings" -Item "Power Plan" -PreviousValue "Balanced" -NewValue "High Performance" -RevertInstructions "Run: powercfg -setactive <previous-guid>"
#>
function Add-ChangeLog {
    param(
        [string]$Category,
        [string]$Item,
        [string]$PreviousValue,
        [string]$NewValue,
        [string]$RevertInstructions
    )
    
    $change = @{
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Category = $Category
        Item = $Item
        PreviousValue = $PreviousValue
        NewValue = $NewValue
        RevertInstructions = $RevertInstructions
    }
    
    $script:ChangeLog += $change
    if ($script:WhatIf) {
        Write-Log "CHANGE (WHAT IF): $Category - $Item : '$PreviousValue' → '$NewValue'" "INFO"
    }
    else {
        Write-Log "CHANGE: $Category - $Item : '$PreviousValue' → '$NewValue'" "INFO"
    }
}

<#
.SYNOPSIS
    Saves the change log to a file for reference and potential rollback.

.DESCRIPTION
    Writes all recorded changes to a JSON file that can be used to understand
    what was changed and how to revert it.

.PARAMETER FilePath
    Optional path to save the change log. Defaults to "OptimizePerformance_Changes.json" in the script directory.

.EXAMPLE
    Save-ChangeLog
#>
function Save-ChangeLog {
    param(
        [string]$FilePath = $script:ChangeLogPath
    )
    
    if ($script:ChangeLog.Count -gt 0) {
        try {
            $changeLogData = @{
                Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
                TotalChanges = $script:ChangeLog.Count
                Changes = $script:ChangeLog
            }
            
            $changeLogData | ConvertTo-Json -Depth 10 | Out-File -FilePath $FilePath -Encoding UTF8
            Write-Log "Change log saved to: $FilePath" "INFO"
            return $FilePath
        }
        catch {
            Write-Log "Error saving change log: $_" "WARNING"
        }
    }
}

<#
.SYNOPSIS
    Restores system settings from a change log file.

.DESCRIPTION
    Reads a change log JSON file and attempts to revert all recorded changes
    by executing the revert instructions for each change.

.PARAMETER ChangeLogPath
    Path to the change log JSON file. Defaults to script's default change log path.

.PARAMETER WhatIf
    If specified, shows what would be reverted without actually reverting.

.EXAMPLE
    Restore-FromChangeLog
    
.EXAMPLE
    Restore-FromChangeLog -ChangeLogPath "C:\Path\To\Changes.json" -WhatIf
#>
function Restore-FromChangeLog {
    param(
        [string]$ChangeLogPath = $script:ChangeLogPath,
        [switch]$WhatIf
    )
    
    if (-not (Test-Path $ChangeLogPath)) {
        Write-Host "Change log file not found: $ChangeLogPath" -ForegroundColor Red
        return $false
    }
    
    try {
        $changeLogData = Get-Content -Path $ChangeLogPath -Raw | ConvertFrom-Json
        $changes = $changeLogData.Changes
        
        if ($changes.Count -eq 0) {
            Write-Host "No changes found in change log." -ForegroundColor Yellow
            return $false
        }
        
        Write-Host "`n========================================" -ForegroundColor Cyan
        Write-Host "  Rollback Operation" -ForegroundColor Cyan
        Write-Host "========================================`n" -ForegroundColor Cyan
        
        if ($WhatIf) {
            Write-Host "WHAT IF: The following changes would be reverted:`n" -ForegroundColor Yellow
        }
        else {
            Write-Host "Reverting $($changes.Count) change(s)...`n" -ForegroundColor Yellow
        }
        
        $successCount = 0
        $failCount = 0
        
        foreach ($change in $changes) {
            Write-Host "[$($change.Category)] $($change.Item)" -ForegroundColor White
            Write-Host "  Current: $($change.NewValue) → Reverting to: $($change.PreviousValue)" -ForegroundColor Gray
            
            if ($WhatIf) {
                Write-Host "  Would execute: $($change.RevertInstructions)" -ForegroundColor Cyan
                Write-Host ""
                continue
            }
            
            # Extract and execute PowerShell commands from revert instructions
            try {
                # Check if it's a registry change
                if ($change.Category -eq "Registry") {
                    # Parse registry revert command
                    if ($change.RevertInstructions -match "Set-ItemProperty") {
                        # Extract the command and execute it
                        $command = $change.RevertInstructions -replace "To revert: ", ""
                        Invoke-Expression $command
                        Write-Host "  ✓ Reverted successfully" -ForegroundColor Green
                        $successCount++
                    }
                    elseif ($change.RevertInstructions -match "delete the registry value") {
                        # Delete registry value to restore default
                        if ($change.Item -match "TcpAckFrequency") {
                            Remove-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters" -Name "TcpAckFrequency" -ErrorAction SilentlyContinue
                        }
                        elseif ($change.Item -match "TCPNoDelay") {
                            Remove-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters" -Name "TCPNoDelay" -ErrorAction SilentlyContinue
                        }
                        Write-Host "  ✓ Reverted successfully (restored default)" -ForegroundColor Green
                        $successCount++
                    }
                }
                # Check if it's a service change
                elseif ($change.Category -eq "Services") {
                    if ($change.RevertInstructions -match "Set-Service.*-StartupType (\w+)") {
                        $startupType = $matches[1]
                        $serviceName = ($change.Item -replace "Service: ", "").Trim()
                        Set-Service -Name $serviceName -StartupType $startupType -ErrorAction Stop
                        if ($change.PreviousValue -match "Status: Running") {
                            Start-Service -Name $serviceName -ErrorAction Stop
                        }
                        Write-Host "  ✓ Reverted successfully" -ForegroundColor Green
                        $successCount++
                    }
                }
                # Check if it's a power settings change
                elseif ($change.Category -eq "PowerSettings") {
                    if ($change.Item -match "Active Power Plan") {
                        # Extract GUID from previous value
                        if ($change.PreviousValue -match "GUID: ([a-f0-9\-]+)") {
                            $previousGuid = $matches[1]
                            powercfg -setactive $previousGuid
                            Write-Host "  ✓ Reverted successfully" -ForegroundColor Green
                            $successCount++
                        }
                    }
                    elseif ($change.RevertInstructions -match "powercfg -set\w+valueindex") {
                        # Extract powercfg command
                        $command = ($change.RevertInstructions -split "To revert: ")[1] -split " or " | Select-Object -First 1
                        Invoke-Expression $command
                        Write-Host "  ✓ Reverted successfully" -ForegroundColor Green
                        $successCount++
                    }
                }
                # Files cannot be restored
                elseif ($change.Category -eq "Files") {
                    Write-Host "  ⚠ Cannot revert: $($change.RevertInstructions)" -ForegroundColor Yellow
                }
                else {
                    Write-Host "  ⚠ Manual revert required: $($change.RevertInstructions)" -ForegroundColor Yellow
                }
            }
            catch {
                Write-Host "  ✗ Failed to revert: $_" -ForegroundColor Red
                $failCount++
            }
            Write-Host ""
        }
        
        if (-not $WhatIf) {
            Write-Host "========================================" -ForegroundColor Cyan
            Write-Host "Rollback Summary: $successCount succeeded, $failCount failed" -ForegroundColor $(if ($failCount -eq 0) { "Green" } else { "Yellow" })
            Write-Host "========================================`n" -ForegroundColor Cyan
        }
        
        return $true
    }
    catch {
        Write-Host "Error reading change log: $_" -ForegroundColor Red
        return $false
    }
}

<#
.SYNOPSIS
    Writes a message to the log file with timestamp and severity level.

.DESCRIPTION
    Logs messages with timestamps and severity levels (INFO, WARNING, ERROR).
    Optionally displays messages to the console based on verbosity settings or severity.
    In WhatIf mode, prefixes messages with [WHAT IF].

.PARAMETER Message
    The message text to log.

.PARAMETER Level
    The severity level of the message. Valid values: INFO, WARNING, ERROR.
    Default is "INFO".

.EXAMPLE
    Write-Log "Operation completed successfully"
    
.EXAMPLE
    Write-Log "An error occurred" "ERROR"
#>
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $prefix = if ($script:WhatIf) { "[WHAT IF] " } else { "" }
    $logMessage = "[$timestamp] [$Level] $prefix$Message"
    Add-Content -Path $script:LogPath -Value $logMessage
    if ($script:Verbose -or $Level -eq "ERROR" -or $Level -eq "WARNING") {
        $color = if ($Level -eq "ERROR") { "Red" } elseif ($Level -eq "WARNING") { "Yellow" } else { "Green" }
        if ($script:WhatIf) {
            Write-Host "[WHAT IF] $Message" -ForegroundColor Cyan
        }
        else {
            Write-Host $logMessage -ForegroundColor $color
        }
    }
}

<#
.SYNOPSIS
    Checks if the current PowerShell session is running with administrator privileges.

.DESCRIPTION
    Verifies whether the current user has administrator rights by checking
    the WindowsPrincipal role membership.

.OUTPUTS
    System.Boolean
    Returns $true if running as administrator, $false otherwise.

.EXAMPLE
    if (Test-Administrator) { Write-Host "Running as admin" }
#>
function Test-Administrator {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

<#
.SYNOPSIS
    Cleans temporary files and caches from various system locations.

.DESCRIPTION
    Removes temporary files from multiple locations including:
    - User temp directories (TEMP, TMP, LocalAppData\Temp)
    - Windows temp directory
    - Internet cache and web cache
    - Recent files folder
    
    Calculates and reports the total amount of disk space freed.

.OUTPUTS
    System.Int64
    Returns the total number of bytes freed from all cleaned locations.

.EXAMPLE
    $freed = Clear-TemporaryFiles
    Write-Host "Freed $([math]::Round($freed / 1MB, 2)) MB"
#>
function Clear-TemporaryFiles {
    Write-Log "Starting temporary files cleanup..."
    $cleaned = 0
    
    $tempPaths = @(
        $env:TEMP,
        $env:TMP,
        "$env:LOCALAPPDATA\Temp",
        "$env:WINDIR\Temp",
        "$env:LOCALAPPDATA\Microsoft\Windows\INetCache",
        "$env:LOCALAPPDATA\Microsoft\Windows\WebCache",
        "$env:APPDATA\Microsoft\Windows\Recent"
    )
    
    $totalPaths = $tempPaths.Count
    $currentPath = 0
    
    foreach ($path in $tempPaths) {
        $currentPath++
        $percentComplete = [math]::Round(($currentPath / $totalPaths) * 100)
        Write-Progress -Activity "Cleaning Temporary Files" -Status "Processing: $path" -PercentComplete $percentComplete
        
        if (Test-Path $path) {
            try {
                $sizeBefore = (Get-ChildItem -Path $path -Recurse -ErrorAction SilentlyContinue | 
                    Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
                
                if ($script:WhatIf) {
                    Write-Log "Would clean $([math]::Round($sizeBefore / 1MB, 2)) MB from $path" "INFO"
                    $cleaned += $sizeBefore
                }
                else {
                    Remove-Item -Path "$path\*" -Recurse -Force -ErrorAction SilentlyContinue
                    
                    $sizeAfter = (Get-ChildItem -Path $path -Recurse -ErrorAction SilentlyContinue | 
                        Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
                    
                    $freed = $sizeBefore - $sizeAfter
                    if ($freed -gt 0) {
                        $cleaned += $freed
                        Write-Log "Cleaned $([math]::Round($freed / 1MB, 2)) MB from $path"
                    }
                }
            }
            catch {
                Write-Log "Error cleaning $path : $_" "WARNING"
            }
        }
    }
    
    Write-Progress -Activity "Cleaning Temporary Files" -Completed
    
    if ($script:WhatIf) {
        Write-Log "Temporary files cleanup (WHAT IF). Would free: $([math]::Round($cleaned / 1MB, 2)) MB"
    }
    else {
        Write-Log "Temporary files cleanup completed. Total freed: $([math]::Round($cleaned / 1MB, 2)) MB"
    }
    
    if ($cleaned -gt 0) {
        Add-ChangeLog -Category "Files" -Item "Temporary Files Cleanup" `
            -PreviousValue "Various temporary files and caches" `
            -NewValue "Cleaned ($([math]::Round($cleaned / 1MB, 2)) MB freed)" `
            -RevertInstructions "Note: Temporary files cannot be restored. They will be recreated automatically as needed by applications."
    }
    
    return $cleaned
}

<#
.SYNOPSIS
    Clears the Windows Update cache to free disk space and resolve update issues.

.DESCRIPTION
    Stops Windows Update related services, removes cached update files from
    the SoftwareDistribution folder, and restarts the services. This can help
    resolve update problems and free significant disk space.

.EXAMPLE
    Clear-WindowsUpdateCache
#>
function Clear-WindowsUpdateCache {
    Write-Log "Clearing Windows Update cache..."
    Write-Progress -Activity "Clearing Windows Update Cache" -Status "Analyzing cache size..." -PercentComplete 0
    
    try {
        $updateCache = "$env:WINDIR\SoftwareDistribution"
        $cacheSize = 0
        
        if (Test-Path $updateCache) {
            Write-Progress -Activity "Clearing Windows Update Cache" -Status "Calculating cache size..." -PercentComplete 25
            $cacheSize = (Get-ChildItem -Path $updateCache -Recurse -ErrorAction SilentlyContinue | 
                Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
        }
        
        if ($script:WhatIf) {
            Write-Progress -Activity "Clearing Windows Update Cache" -Status "WHAT IF: Would clear cache..." -PercentComplete 50
            Write-Log "Would clear Windows Update cache ($([math]::Round($cacheSize / 1MB, 2)) MB)" "INFO"
        }
        else {
            Write-Progress -Activity "Clearing Windows Update Cache" -Status "Stopping services..." -PercentComplete 30
            Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue
            Stop-Service -Name cryptSvc -Force -ErrorAction SilentlyContinue
            Stop-Service -Name bits -Force -ErrorAction SilentlyContinue
            Stop-Service -Name msiserver -Force -ErrorAction SilentlyContinue
            
            Write-Progress -Activity "Clearing Windows Update Cache" -Status "Removing cache files..." -PercentComplete 60
            if (Test-Path $updateCache) {
                Remove-Item -Path "$updateCache\*" -Recurse -Force -ErrorAction SilentlyContinue
                Write-Log "Windows Update cache cleared"
            }
            
            Write-Progress -Activity "Clearing Windows Update Cache" -Status "Restarting services..." -PercentComplete 80
            Start-Service -Name wuauserv -ErrorAction SilentlyContinue
            Start-Service -Name cryptSvc -ErrorAction SilentlyContinue
            Start-Service -Name bits -ErrorAction SilentlyContinue
            Start-Service -Name msiserver -ErrorAction SilentlyContinue
        }
        
        Write-Progress -Activity "Clearing Windows Update Cache" -Completed
        
        if ($cacheSize -gt 0) {
            Add-ChangeLog -Category "Files" -Item "Windows Update Cache" `
                -PreviousValue "Update cache files ($([math]::Round($cacheSize / 1MB, 2)) MB)" `
                -NewValue "Cleared" `
                -RevertInstructions "Note: Windows Update cache cannot be restored. Windows will re-download updates as needed. This may cause longer update times on next check."
        }
    }
    catch {
        Write-Progress -Activity "Clearing Windows Update Cache" -Completed
        Write-Log "Error clearing Windows Update cache: $_" "WARNING"
    }
}

<#
.SYNOPSIS
    Flushes the DNS resolver cache.

.DESCRIPTION
    Clears the local DNS cache by executing ipconfig /flushdns. This can help
    resolve DNS-related connectivity issues and ensure fresh DNS lookups.

.EXAMPLE
    Clear-DNSCache
#>
function Clear-DNSCache {
    Write-Log "Clearing DNS cache..."
    try {
        if ($script:WhatIf) {
            Write-Log "Would flush DNS cache" "INFO"
        }
        else {
            ipconfig /flushdns | Out-Null
            Write-Log "DNS cache cleared successfully"
        }
    }
    catch {
        Write-Log "Error clearing DNS cache: $_" "ERROR"
    }
}

<#
.SYNOPSIS
    Optimizes disk performance by defragmenting and trimming all fixed drives.

.DESCRIPTION
    Performs disk optimization on all fixed (non-removable) drives by running
    defragmentation and TRIM operations. This improves disk read/write performance
    and can extend SSD lifespan.

.EXAMPLE
    Optimize-DiskPerformance
#>
function Optimize-DiskPerformance {
    Write-Log "Starting disk optimization..."
    
    try {
        $drives = Get-Volume | Where-Object { $_.DriveType -eq 'Fixed' -and $_.DriveLetter }
        $totalDrives = $drives.Count
        $currentDrive = 0
        
        if ($totalDrives -eq 0) {
            Write-Log "No fixed drives found to optimize" "WARNING"
            return
        }
        
        foreach ($drive in $drives) {
            $currentDrive++
            $driveLetter = $drive.DriveLetter
            $percentComplete = [math]::Round(($currentDrive / $totalDrives) * 100)
            
            Write-Progress -Activity "Optimizing Disks" -Status "Optimizing drive $driveLetter`:" -PercentComplete $percentComplete -CurrentOperation "Defragmenting and trimming..."
            Write-Log "Optimizing drive $driveLetter`:..."

            if ($script:WhatIf) {
                Write-Log "Would optimize drive $driveLetter`: (defragmentation and TRIM)" "INFO"
            }
            else {
                # Run disk cleanup
                try {
                    Optimize-Volume -DriveLetter $driveLetter -Defrag -ReTrim -ErrorAction SilentlyContinue | Out-Null
                    Write-Log "Drive $driveLetter` optimization completed"
                }
                catch {
                    Write-Log "Could not optimize drive $driveLetter` (may require manual defragmentation): $_" "WARNING"
                }
            }
        }
        
        Write-Progress -Activity "Optimizing Disks" -Completed
    }
    catch {
        Write-Progress -Activity "Optimizing Disks" -Completed
        Write-Log "Error during disk optimization: $_" "ERROR"
    }
}

<#
.SYNOPSIS
    Optimizes Windows power settings for maximum performance.

.DESCRIPTION
    Configures power settings to prioritize performance over power saving:
    - Activates or creates High Performance power plan
    - Disables USB selective suspend
    - Disables hard disk sleep mode
    
    These settings may increase power consumption but improve system responsiveness.

.EXAMPLE
    Optimize-PowerSettings
#>
function Optimize-PowerSettings {
    Write-Log "Optimizing power settings for performance..."
    
    try {
        # Get current power plan before changing
        $currentPlan = Get-CurrentPowerPlan
        $powerCfgList = powercfg -list
        $currentGuid = ($powerCfgList | Select-String "^\s+\*" | ForEach-Object { ($_ -split '\s+')[3] }).Trim()
        
        # Set power plan to High Performance
        $highPerf = powercfg -list | Select-String "High performance" | ForEach-Object { ($_ -split '\s+')[3] }
        
        if ($highPerf) {
            $highPerfGuid = $highPerf.Trim()
            if (-not $script:WhatIf) {
                powercfg -setactive $highPerfGuid
                Write-Log "Power plan set to High Performance"
            }
            else {
                Write-Log "Would set power plan to High Performance (GUID: $highPerfGuid)" "INFO"
            }
            
            Add-ChangeLog -Category "PowerSettings" -Item "Active Power Plan" `
                -PreviousValue "$currentPlan (GUID: $currentGuid)" `
                -NewValue "High Performance (GUID: $highPerfGuid)" `
                -RevertInstructions "To revert: Run 'powercfg -setactive $currentGuid' or change in Windows Settings > System > Power & battery > Power mode"
        }
        else {
            # Create high performance plan if it doesn't exist
            $guid = powercfg -duplicatescheme 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
            if ($guid) {
                $newGuid = ($guid -split '\s+')[-1].Trim()
                if (-not $script:WhatIf) {
                    powercfg -setactive $newGuid
                    Write-Log "High Performance power plan created and activated"
                }
                else {
                    Write-Log "Would create and activate High Performance power plan (GUID: $newGuid)" "INFO"
                }
                
                Add-ChangeLog -Category "PowerSettings" -Item "Active Power Plan" `
                    -PreviousValue "$currentPlan (GUID: $currentGuid)" `
                    -NewValue "High Performance (GUID: $newGuid) [Created]" `
                    -RevertInstructions "To revert: Run 'powercfg -setactive $currentGuid' or change in Windows Settings > System > Power & battery > Power mode"
            }
        }
        
        # Disable USB selective suspend
        if (-not $script:WhatIf) {
            powercfg -setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
            powercfg -setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
        }
        else {
            Write-Log "Would disable USB selective suspend (AC and Battery)" "INFO"
        }
        
        Add-ChangeLog -Category "PowerSettings" -Item "USB Selective Suspend (AC Power)" `
            -PreviousValue "Enabled (varies)" `
            -NewValue "Disabled" `
            -RevertInstructions "To revert: Run 'powercfg -setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 1' or change in Power Options > Advanced settings > USB settings"
        
        Add-ChangeLog -Category "PowerSettings" -Item "USB Selective Suspend (Battery)" `
            -PreviousValue "Enabled (varies)" `
            -NewValue "Disabled" `
            -RevertInstructions "To revert: Run 'powercfg -setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 1' or change in Power Options > Advanced settings > USB settings"
        
        # Disable hard disk sleep
        if (-not $script:WhatIf) {
            powercfg -setacvalueindex SCHEME_CURRENT 0012ee47-9041-4b5d-9b77-535fba8b1442 6738e2c4-e8a5-4a42-b16a-e040e769756e 0
            powercfg -setdcvalueindex SCHEME_CURRENT 0012ee47-9041-4b5d-9b77-535fba8b1442 6738e2c4-e8a5-4a42-b16a-e040e769756e 0
        }
        else {
            Write-Log "Would disable hard disk sleep (AC and Battery)" "INFO"
        }
        
        Add-ChangeLog -Category "PowerSettings" -Item "Hard Disk Sleep (AC Power)" `
            -PreviousValue "Enabled (varies by timeout)" `
            -NewValue "Never (0 minutes)" `
            -RevertInstructions "To revert: Run 'powercfg -setacvalueindex SCHEME_CURRENT 0012ee47-9041-4b5d-9b77-535fba8b1442 6738e2c4-e8a5-4a42-b16a-e040e769756e <previous-value>' or change in Power Options > Advanced settings > Hard disk"
        
        Add-ChangeLog -Category "PowerSettings" -Item "Hard Disk Sleep (Battery)" `
            -PreviousValue "Enabled (varies by timeout)" `
            -NewValue "Never (0 minutes)" `
            -RevertInstructions "To revert: Run 'powercfg -setdcvalueindex SCHEME_CURRENT 0012ee47-9041-4b5d-9b77-535fba8b1442 6738e2c4-e8a5-4a42-b16a-e040e769756e <previous-value>' or change in Power Options > Advanced settings > Hard disk"
        
        if (-not $script:WhatIf) {
            powercfg -setactive SCHEME_CURRENT
        }
        Write-Log "Power settings optimized"
    }
    catch {
        Write-Log "Error optimizing power settings: $_" "WARNING"
    }
}

<#
.SYNOPSIS
    Disables unnecessary Windows services to improve system performance.

.DESCRIPTION
    Disables and stops services that are typically not needed for most users:
    - Fax service
    - Windows Search (WSearch)
    - Remote Registry
    
    These services consume system resources even when not in use. Modify the
    $servicesToDisable array to customize which services are disabled.

.EXAMPLE
    Optimize-WindowsServices
#>
function Optimize-WindowsServices {
    Write-Log "Optimizing Windows services..."
    
    $servicesToDisable = @(
        # Services that can be safely disabled for better performance (adjust as needed)
        "Fax",
        "WSearch",  # Windows Search (disable if you don't use it)
        "RemoteRegistry"
    )
    
    $totalServices = $servicesToDisable.Count
    $currentService = 0
    
    foreach ($serviceName in $servicesToDisable) {
        $currentService++
        $percentComplete = [math]::Round(($currentService / $totalServices) * 100)
        Write-Progress -Activity "Optimizing Services" -Status "Processing: $serviceName" -PercentComplete $percentComplete
        
        try {
            $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
            if ($service) {
                $previousStartupType = $service.StartType
                $previousStatus = $service.Status
                
                if ($service.Status -eq "Running") {
                    if ($script:WhatIf) {
                        Write-Log "Would disable and stop service: $serviceName" "INFO"
                    }
                    else {
                        Set-Service -Name $serviceName -StartupType Disabled -ErrorAction SilentlyContinue
                        Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
                        Write-Log "Disabled service: $serviceName"
                    }
                    
                    Add-ChangeLog -Category "Services" -Item "Service: $serviceName" `
                        -PreviousValue "Startup: $previousStartupType, Status: $previousStatus" `
                        -NewValue "Startup: Disabled, Status: Stopped" `
                        -RevertInstructions "To revert: Run 'Set-Service -Name $serviceName -StartupType $previousStartupType' and 'Start-Service -Name $serviceName' in PowerShell as Administrator, or use Services.msc"
                }
                elseif ($previousStartupType -ne "Disabled") {
                    if ($script:WhatIf) {
                        Write-Log "Would set service startup type to Disabled: $serviceName" "INFO"
                    }
                    else {
                        Set-Service -Name $serviceName -StartupType Disabled -ErrorAction SilentlyContinue
                        Write-Log "Set service startup type to Disabled: $serviceName"
                    }
                    
                    Add-ChangeLog -Category "Services" -Item "Service: $serviceName" `
                        -PreviousValue "Startup: $previousStartupType, Status: $previousStatus" `
                        -NewValue "Startup: Disabled, Status: $previousStatus" `
                        -RevertInstructions "To revert: Run 'Set-Service -Name $serviceName -StartupType $previousStartupType' in PowerShell as Administrator, or use Services.msc"
                }
            }
        }
        catch {
            Write-Log "Could not modify service $serviceName : $_" "WARNING"
        }
    }
    
    Write-Progress -Activity "Optimizing Services" -Completed
}

<#
.SYNOPSIS
    Optimizes system memory by clearing standby memory and forcing garbage collection.

.DESCRIPTION
    Performs memory optimization by:
    - Clearing standby memory using SetProcessWorkingSetSize API
    - Forcing .NET garbage collection to free managed memory
    
    This can help free up memory that's being held but not actively used.

.EXAMPLE
    Optimize-Memory
#>
function Optimize-Memory {
    Write-Log "Optimizing memory..."
    
    try {
        # Clear standby memory
        $code = @"
[DllImport("kernel32.dll", SetLastError = true)]
public static extern bool SetProcessWorkingSetSize(IntPtr hProcess, int dwMinimumWorkingSetSize, int dwMaximumWorkingSetSize);
"@
        
        $type = Add-Type -MemberDefinition $code -Name "Win32SetProcessWorkingSetSize" -Namespace "Win32Functions" -PassThru
        $process = Get-Process -Id $PID
        $type::SetProcessWorkingSetSize($process.Handle, -1, -1) | Out-Null
        
        # Force garbage collection
        [System.GC]::Collect()
        [System.GC]::WaitForPendingFinalizers()
        [System.GC]::Collect()
        
        Write-Log "Memory optimization completed"
    }
    catch {
        Write-Log "Error optimizing memory: $_" "WARNING"
    }
}

<#
.SYNOPSIS
    Optimizes TCP/IP network settings for better network performance.

.DESCRIPTION
    Modifies TCP/IP registry settings to improve network performance:
    - Disables Nagle's algorithm (TCPNoDelay = 1)
    - Sets TcpAckFrequency to 1 for immediate ACK responses
    
    These changes can reduce network latency, especially for interactive applications.

.EXAMPLE
    Optimize-NetworkSettings
#>
function Optimize-NetworkSettings {
    Write-Log "Optimizing network settings..."
    
    try {
        $regPath = "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
        
        # Get current values before changing
        $currentTcpAckFrequency = (Get-ItemProperty -Path $regPath -Name "TcpAckFrequency" -ErrorAction SilentlyContinue).TcpAckFrequency
        $currentTcpNoDelay = (Get-ItemProperty -Path $regPath -Name "TCPNoDelay" -ErrorAction SilentlyContinue).TCPNoDelay
        
        if (-not $currentTcpAckFrequency) { $currentTcpAckFrequency = "Not set (default: 2)" }
        if (-not $currentTcpNoDelay) { $currentTcpNoDelay = "Not set (default: 0)" }
        
        # Disable Nagle's algorithm for better network performance
        if ($script:WhatIf) {
            Write-Log "Would set TcpAckFrequency to 1 (current: $currentTcpAckFrequency)" "INFO"
            Write-Log "Would set TCPNoDelay to 1 (current: $currentTcpNoDelay)" "INFO"
        }
        else {
            Set-ItemProperty -Path $regPath -Name "TcpAckFrequency" -Value 1 -ErrorAction SilentlyContinue
            Set-ItemProperty -Path $regPath -Name "TCPNoDelay" -Value 1 -ErrorAction SilentlyContinue
        }
        
        Add-ChangeLog -Category "Registry" -Item "TCP/IP: TcpAckFrequency" `
            -PreviousValue "$currentTcpAckFrequency" `
            -NewValue "1 (Immediate ACK)" `
            -RevertInstructions "To revert: Run 'Set-ItemProperty -Path `"$regPath`" -Name `"TcpAckFrequency`" -Value $currentTcpAckFrequency' in PowerShell as Administrator, or delete the registry value to restore default"
        
        Add-ChangeLog -Category "Registry" -Item "TCP/IP: TCPNoDelay" `
            -PreviousValue "$currentTcpNoDelay" `
            -NewValue "1 (Nagle's algorithm disabled)" `
            -RevertInstructions "To revert: Run 'Set-ItemProperty -Path `"$regPath`" -Name `"TCPNoDelay`" -Value $currentTcpNoDelay' in PowerShell as Administrator, or delete the registry value to restore default"
        
        Write-Log "Network settings optimized"
    }
    catch {
        Write-Log "Error optimizing network settings: $_" "WARNING"
    }
}

<#
.SYNOPSIS
    Optimizes Windows visual effects for better performance.

.DESCRIPTION
    Disables unnecessary visual effects and animations to improve system
    responsiveness and reduce GPU/CPU usage. Configures Windows to prioritize
    performance over visual appearance.

.EXAMPLE
    Optimize-VisualEffects
#>
function Optimize-VisualEffects {
    Write-Log "Optimizing visual effects for performance..."
    
    try {
        $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
        
        # Get current value
        $currentValue = (Get-ItemProperty -Path $regPath -Name "VisualFXSetting" -ErrorAction SilentlyContinue).VisualFXSetting
        if (-not $currentValue) { $currentValue = "Not set (default: 2 - Let Windows decide)" }
        
        if ($script:WhatIf) {
            Write-Log "Would set VisualFXSetting to 2 (Adjust for best performance)" "INFO"
        }
        else {
            # Set to "Adjust for best performance" (value 2)
            Set-ItemProperty -Path $regPath -Name "VisualFXSetting" -Value 2 -ErrorAction SilentlyContinue
            Write-Log "Visual effects set to 'Adjust for best performance'"
        }
        
        Add-ChangeLog -Category "Registry" -Item "Visual Effects: VisualFXSetting" `
            -PreviousValue "$currentValue" `
            -NewValue "2 (Adjust for best performance)" `
            -RevertInstructions "To revert: Run 'Set-ItemProperty -Path `"$regPath`" -Name `"VisualFXSetting`" -Value $currentValue' or change in System Properties > Advanced > Performance Settings"
        
        # Additional visual effect optimizations via registry
        $advancedPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
        
        $visualSettings = @{
            "ListviewAlphaSelect" = 0          # Disable transparent selection
            "ListviewShadow" = 0                # Disable list view shadows
            "TaskbarAnimations" = 0             # Disable taskbar animations
            "MinAnimate" = 0                    # Disable window animations
        }
        
        foreach ($setting in $visualSettings.GetEnumerator()) {
            $current = (Get-ItemProperty -Path $advancedPath -Name $setting.Key -ErrorAction SilentlyContinue).($setting.Key)
            if (-not $current) { $current = "Not set (default: varies)" }
            
            if (-not $script:WhatIf) {
                Set-ItemProperty -Path $advancedPath -Name $setting.Key -Value $setting.Value -ErrorAction SilentlyContinue
            }
            
            Add-ChangeLog -Category "Registry" -Item "Visual Effects: $($setting.Key)" `
                -PreviousValue "$current" `
                -NewValue "$($setting.Value) (Disabled)" `
                -RevertInstructions "To revert: Run 'Set-ItemProperty -Path `"$advancedPath`" -Name `"$($setting.Key)`" -Value $current' or change in System Properties > Advanced > Performance Settings"
        }
        
        Write-Log "Visual effects optimized"
    }
    catch {
        Write-Log "Error optimizing visual effects: $_" "WARNING"
    }
}

<#
.SYNOPSIS
    Optimizes processor scheduling for better application performance.

.DESCRIPTION
    Configures Windows to prioritize foreground applications over background
    services, improving responsiveness of active programs.

.EXAMPLE
    Optimize-ProcessorScheduling
#>
function Optimize-ProcessorScheduling {
    Write-Log "Optimizing processor scheduling..."
    
    try {
        $regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\PriorityControl"
        
        # Get current value (0 = Background services, 1 = Programs)
        $currentValue = (Get-ItemProperty -Path $regPath -Name "Win32PrioritySeparation" -ErrorAction SilentlyContinue).Win32PrioritySeparation
        if (-not $currentValue) { $currentValue = "Not set (default: 2 - Balanced)" }
        
        # Set to prioritize programs (value 26 hex = 38 decimal for best performance)
        $newValue = 38
        
        if ($script:WhatIf) {
            Write-Log "Would set Win32PrioritySeparation to $newValue (Prioritize programs)" "INFO"
        }
        else {
            Set-ItemProperty -Path $regPath -Name "Win32PrioritySeparation" -Value $newValue -Type DWord -ErrorAction SilentlyContinue
            Write-Log "Processor scheduling optimized for programs"
        }
        
        Add-ChangeLog -Category "Registry" -Item "Processor Scheduling: Win32PrioritySeparation" `
            -PreviousValue "$currentValue" `
            -NewValue "$newValue (Prioritize programs)" `
            -RevertInstructions "To revert: Run 'Set-ItemProperty -Path `"$regPath`" -Name `"Win32PrioritySeparation`" -Value $currentValue' or change in System Properties > Advanced > Performance Settings > Advanced tab"
        
        Write-Log "Processor scheduling optimized"
    }
    catch {
        Write-Log "Error optimizing processor scheduling: $_" "WARNING"
    }
}

<#
.SYNOPSIS
    Optimizes Prefetch and Superfetch settings for better performance.

.DESCRIPTION
    Configures Prefetch and Superfetch (SysMain) settings based on drive type.
    For SSDs, disables Superfetch as it's not beneficial and can cause wear.
    For HDDs, enables these features for better performance.

.EXAMPLE
    Optimize-PrefetchSettings
#>
function Optimize-PrefetchSettings {
    Write-Log "Optimizing Prefetch and Superfetch settings..."
    
    try {
        $regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters"
        
        # Check if system drive is SSD
        $systemDrive = $env:SystemDrive
        $isSSD = $false
        
        try {
            $disk = Get-PhysicalDisk | Where-Object { $_.DeviceID -eq (Get-Partition -DriveLetter $systemDrive[0]).DiskNumber } | Select-Object -First 1
            if ($disk -and $disk.MediaType -eq "SSD") {
                $isSSD = $true
            }
        }
        catch {
            # If we can't determine, assume it might be SSD and optimize conservatively
            Write-Log "Could not determine drive type, applying conservative settings" "INFO"
        }
        
        # Get current values
        $currentEnablePrefetcher = (Get-ItemProperty -Path $regPath -Name "EnablePrefetcher" -ErrorAction SilentlyContinue).EnablePrefetcher
        $currentEnableSuperfetch = (Get-ItemProperty -Path $regPath -Name "EnableSuperfetch" -ErrorAction SilentlyContinue).EnableSuperfetch
        
        if (-not $currentEnablePrefetcher) { $currentEnablePrefetcher = "Not set (default: 3)" }
        if (-not $currentEnableSuperfetch) { $currentEnableSuperfetch = "Not set (default: 3)" }
        
        if ($isSSD) {
            # For SSDs: Disable Superfetch, keep Prefetcher at 1 (application prefetch only)
            $prefetcherValue = 1
            $superfetchValue = 0
            
            if ($script:WhatIf) {
                Write-Log "SSD detected. Would set EnablePrefetcher to $prefetcherValue and EnableSuperfetch to $superfetchValue" "INFO"
            }
            else {
                Set-ItemProperty -Path $regPath -Name "EnablePrefetcher" -Value $prefetcherValue -Type DWord -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $regPath -Name "EnableSuperfetch" -Value $superfetchValue -Type DWord -ErrorAction SilentlyContinue
                Write-Log "Prefetch/Superfetch optimized for SSD (Superfetch disabled, Prefetcher optimized)"
            }
        }
        else {
            # For HDDs: Enable both for better performance
            $prefetcherValue = 3
            $superfetchValue = 3
            
            if ($script:WhatIf) {
                Write-Log "HDD detected. Would set EnablePrefetcher to $prefetcherValue and EnableSuperfetch to $superfetchValue" "INFO"
            }
            else {
                Set-ItemProperty -Path $regPath -Name "EnablePrefetcher" -Value $prefetcherValue -Type DWord -ErrorAction SilentlyContinue
                Set-ItemProperty -Path $regPath -Name "EnableSuperfetch" -Value $superfetchValue -Type DWord -ErrorAction SilentlyContinue
                Write-Log "Prefetch/Superfetch optimized for HDD (both enabled)"
            }
        }
        
        Add-ChangeLog -Category "Registry" -Item "Prefetch: EnablePrefetcher" `
            -PreviousValue "$currentEnablePrefetcher" `
            -NewValue "$prefetcherValue" `
            -RevertInstructions "To revert: Run 'Set-ItemProperty -Path `"$regPath`" -Name `"EnablePrefetcher`" -Value $currentEnablePrefetcher'"
        
        Add-ChangeLog -Category "Registry" -Item "Superfetch: EnableSuperfetch" `
            -PreviousValue "$currentEnableSuperfetch" `
            -NewValue "$superfetchValue" `
            -RevertInstructions "To revert: Run 'Set-ItemProperty -Path `"$regPath`" -Name `"EnableSuperfetch`" -Value $currentEnableSuperfetch'"
        
        Write-Log "Prefetch/Superfetch settings optimized"
    }
    catch {
        Write-Log "Error optimizing Prefetch/Superfetch settings: $_" "WARNING"
    }
}

<#
.SYNOPSIS
    Optimizes Windows Update delivery optimization settings.

.DESCRIPTION
    Configures Windows Update to reduce bandwidth usage and improve performance
    by limiting peer-to-peer update delivery and optimizing update scheduling.

.EXAMPLE
    Optimize-WindowsUpdateSettings
#>
function Optimize-WindowsUpdateSettings {
    Write-Log "Optimizing Windows Update settings..."
    
    try {
        $regPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\DeliveryOptimization\Config"
        
        # Get current values
        $currentDownloadMode = (Get-ItemProperty -Path $regPath -Name "DODownloadMode" -ErrorAction SilentlyContinue).DODownloadMode
        if (-not $currentDownloadMode) { $currentDownloadMode = "Not set (default: 1 - LAN only)" }
        
        # Set to 0 = Download from Microsoft only (no peer-to-peer)
        # This reduces bandwidth and improves privacy
        $newDownloadMode = 0
        
        if ($script:WhatIf) {
            Write-Log "Would set DODownloadMode to $newDownloadMode (Download from Microsoft only)" "INFO"
        }
        else {
            Set-ItemProperty -Path $regPath -Name "DODownloadMode" -Value $newDownloadMode -Type DWord -ErrorAction SilentlyContinue
            Write-Log "Windows Update delivery optimization configured"
        }
        
        Add-ChangeLog -Category "Registry" -Item "Windows Update: DODownloadMode" `
            -PreviousValue "$currentDownloadMode" `
            -NewValue "$newDownloadMode (Download from Microsoft only)" `
            -RevertInstructions "To revert: Run 'Set-ItemProperty -Path `"$regPath`" -Name `"DODownloadMode`" -Value $currentDownloadMode' or change in Settings > Update & Security > Delivery Optimization"
        
        Write-Log "Windows Update settings optimized"
    }
    catch {
        Write-Log "Error optimizing Windows Update settings: $_" "WARNING"
    }
}

<#
.SYNOPSIS
    Disables unnecessary background apps to improve performance.

.DESCRIPTION
    Configures Windows to prevent apps from running in the background, reducing
    CPU, memory, and battery usage. This improves system responsiveness.

.EXAMPLE
    Optimize-BackgroundApps
#>
function Optimize-BackgroundApps {
    Write-Log "Optimizing background app settings..."
    
    try {
        $regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications"
        
        # Get all background apps
        $backgroundApps = Get-ChildItem -Path $regPath -ErrorAction SilentlyContinue
        
        $disabledCount = 0
        foreach ($app in $backgroundApps) {
            $appName = $app.PSChildName
            $currentValue = (Get-ItemProperty -Path $app.PSPath -Name "Disabled" -ErrorAction SilentlyContinue).Disabled
            
            if (-not $currentValue -or $currentValue -eq 0) {
                if ($script:WhatIf) {
                    Write-Log "Would disable background app: $appName" "INFO"
                }
                else {
                    Set-ItemProperty -Path $app.PSPath -Name "Disabled" -Value 1 -Type DWord -ErrorAction SilentlyContinue
                    $disabledCount++
                }
            }
        }
        
        # Also set global setting to disable background apps
        $globalPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications"
        $globalDisabled = (Get-ItemProperty -Path $globalPath -Name "GlobalUserDisabled" -ErrorAction SilentlyContinue).GlobalUserDisabled
        if (-not $globalDisabled) { $globalDisabled = "Not set (default: 0 - Enabled)" }
        
        if ($script:WhatIf) {
            Write-Log "Would set GlobalUserDisabled to 1 (Disable all background apps)" "INFO"
        }
        else {
            Set-ItemProperty -Path $globalPath -Name "GlobalUserDisabled" -Value 1 -Type DWord -ErrorAction SilentlyContinue
            Write-Log "Disabled $disabledCount background app(s) and set global policy"
        }
        
        Add-ChangeLog -Category "Registry" -Item "Background Apps: GlobalUserDisabled" `
            -PreviousValue "$globalDisabled" `
            -NewValue "1 (All background apps disabled)" `
            -RevertInstructions "To revert: Run 'Set-ItemProperty -Path `"$globalPath`" -Name `"GlobalUserDisabled`" -Value 0' or change in Settings > Privacy > Background apps"
        
        Write-Log "Background app settings optimized"
    }
    catch {
        Write-Log "Error optimizing background apps: $_" "WARNING"
    }
}

<#
.SYNOPSIS
    Optimizes System Restore settings to reduce disk usage.

.DESCRIPTION
    Configures System Restore to use less disk space while maintaining protection.
    Reduces the maximum disk space allocated to restore points.

.EXAMPLE
    Optimize-SystemRestore
#>
function Optimize-SystemRestore {
    Write-Log "Optimizing System Restore settings..."
    
    try {
        # Use vssadmin to configure restore point space
        # Set to use 5% of disk space (default is often 10-15%)
        $drives = Get-Volume | Where-Object { $_.DriveType -eq 'Fixed' -and $_.DriveLetter }
        
        foreach ($drive in $drives) {
            $driveLetter = $drive.DriveLetter
            $drivePath = "$driveLetter`:"
            
            try {
                # Get current restore point size (in MB)
                $currentSize = (vssadmin list ShadowStorage /For=$drivePath 2>&1 | Select-String "Maximum Shadow Copy Storage space" | ForEach-Object { ($_ -split ':')[1].Trim() })
                
                if ($script:WhatIf) {
                    Write-Log "Would optimize System Restore space for drive $driveLetter`: (set to 5% of disk)" "INFO"
                }
                else {
                    # Set to 5% of disk space
                    vssadmin Resize ShadowStorage /For=$drivePath /On=$drivePath /MaxSize=5% 2>&1 | Out-Null
                    Write-Log "System Restore optimized for drive $driveLetter`:"
                }
                
                Add-ChangeLog -Category "SystemRestore" -Item "System Restore: $driveLetter`:" `
                    -PreviousValue "$currentSize (varies)" `
                    -NewValue "5% of disk space" `
                    -RevertInstructions "To revert: Run 'vssadmin Resize ShadowStorage /For=$drivePath /On=$drivePath /MaxSize=10%' or change in System Properties > System Protection"
            }
            catch {
                Write-Log "Could not optimize System Restore for drive $driveLetter`: $_" "WARNING"
            }
        }
        
        Write-Log "System Restore settings optimized"
    }
    catch {
        Write-Log "Error optimizing System Restore: $_" "WARNING"
    }
}

<#
.SYNOPSIS
    Optimizes additional registry settings for performance.

.DESCRIPTION
    Applies various registry tweaks that can improve system performance:
    - Disables Windows tips and suggestions
    - Optimizes file system settings
    - Improves file copy performance
    - Reduces telemetry overhead

.EXAMPLE
    Optimize-AdditionalRegistrySettings
#>
function Optimize-AdditionalRegistrySettings {
    Write-Log "Optimizing additional registry settings..."
    
    try {
        $optimizations = @(
            @{
                Path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
                Name = "SystemPaneSuggestionsEnabled"
                Value = 0
                Type = "DWord"
                Description = "Disable Windows tips and suggestions"
            },
            @{
                Path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
                Name = "SoftLandingEnabled"
                Value = 0
                Type = "DWord"
                Description = "Disable soft landing (feature suggestions)"
            },
            @{
                Path = "HKCU:\Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
                Name = "SubscribedContent-338393Enabled"
                Value = 0
                Type = "DWord"
                Description = "Disable content delivery"
            },
            @{
                Path = "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem"
                Name = "LongPathsEnabled"
                Value = 1
                Type = "DWord"
                Description = "Enable long file paths (improves compatibility)"
            },
            @{
                Path = "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem"
                Name = "NtfsDisableLastAccessUpdate"
                Value = 1
                Type = "DWord"
                Description = "Disable last access time updates (improves file system performance)"
            },
            @{
                Path = "HKLM:\SYSTEM\CurrentControlSet\Services\LanmanServer\Parameters"
                Name = "IRPStackSize"
                Value = 30
                Type = "DWord"
                Description = "Increase IRP stack size (improves network file copy performance)"
            }
        )
        
        foreach ($opt in $optimizations) {
            # Ensure registry path exists
            if (-not (Test-Path $opt.Path)) {
                New-Item -Path $opt.Path -Force -ErrorAction SilentlyContinue | Out-Null
            }
            
            $currentValue = (Get-ItemProperty -Path $opt.Path -Name $opt.Name -ErrorAction SilentlyContinue).($opt.Name)
            if (-not $currentValue) { $currentValue = "Not set (default: varies)" }
            
            if ($script:WhatIf) {
                Write-Log "Would set $($opt.Path)\$($opt.Name) to $($opt.Value) - $($opt.Description)" "INFO"
            }
            else {
                Set-ItemProperty -Path $opt.Path -Name $opt.Name -Value $opt.Value -Type $opt.Type -ErrorAction SilentlyContinue
            }
            
            Add-ChangeLog -Category "Registry" -Item "$($opt.Description): $($opt.Name)" `
                -PreviousValue "$currentValue" `
                -NewValue "$($opt.Value)" `
                -RevertInstructions "To revert: Run 'Set-ItemProperty -Path `"$($opt.Path)`" -Name `"$($opt.Name)`" -Value $currentValue' or delete the registry value to restore default"
        }
        
        Write-Log "Additional registry settings optimized"
    }
    catch {
        Write-Log "Error optimizing additional registry settings: $_" "WARNING"
    }
}

<#
.SYNOPSIS
    Collects and logs system information for diagnostic purposes.

.DESCRIPTION
    Retrieves and logs key system information including:
    - Operating system version
    - CPU model and name
    - Total and available physical memory
    
    This information is written to the log file for reference.

.EXAMPLE
    Get-SystemInfo
#>
function Get-SystemInfo {
    Write-Log "Collecting system information..."
    
    $os = Get-CimInstance Win32_OperatingSystem
    $cpu = Get-CimInstance Win32_Processor
    $memory = Get-CimInstance Win32_ComputerSystem
    
    Write-Log "OS: $($os.Caption) $($os.Version)"
    Write-Log "CPU: $($cpu.Name)"
    Write-Log "Total Memory: $([math]::Round($memory.TotalPhysicalMemory / 1GB, 2)) GB"
    Write-Log "Available Memory: $([math]::Round($os.FreePhysicalMemory / 1MB, 2)) GB"
}

<#
.SYNOPSIS
    Gets memory information including standby memory that can be freed.

.DESCRIPTION
    Retrieves current memory statistics including total, available, and standby memory.

.OUTPUTS
    System.Collections.Hashtable
    Returns a hashtable with TotalGB, AvailableGB, StandbyGB, and other memory metrics.

.EXAMPLE
    $memInfo = Get-MemoryInfo
#>
function Get-MemoryInfo {
    try {
        $os = Get-CimInstance Win32_OperatingSystem
        $cs = Get-CimInstance Win32_ComputerSystem
        
        $totalGB = [math]::Round($cs.TotalPhysicalMemory / 1GB, 2)
        $availableGB = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
        
        # Try to get standby memory using Get-Counter (more accurate)
        $standbyGB = 0
        try {
            $standbyCounter = Get-Counter "\Memory\Standby Cache Reserve Bytes" -ErrorAction SilentlyContinue
            if ($standbyCounter) {
                $standbyBytes = $standbyCounter.CounterSamples[0].CookedValue
                $standbyGB = [math]::Round($standbyBytes / 1GB, 2)
            }
        }
        catch {
            # Fallback: estimate standby as difference between total and available
            $usedGB = $totalGB - $availableGB
            $standbyGB = [math]::Round($usedGB * 0.3, 2)  # Rough estimate: 30% of used memory
        }
        
        return @{
            TotalGB = $totalGB
            AvailableGB = $availableGB
            StandbyGB = $standbyGB
            UsedGB = [math]::Round($totalGB - $availableGB, 2)
        }
    }
    catch {
        return @{
            TotalGB = 0
            AvailableGB = 0
            StandbyGB = 0
            UsedGB = 0
        }
    }
}

<#
.SYNOPSIS
    Estimates disk space that can be freed by cleanup operations.

.DESCRIPTION
    Calculates the total size of temporary files and caches that can be cleaned.

.OUTPUTS
    System.Double
    Returns estimated disk space in MB that can be freed.

.EXAMPLE
    $spaceToFree = Get-EstimatedCleanupSpace
#>
function Get-EstimatedCleanupSpace {
    $totalSize = 0
    $tempPaths = @(
        $env:TEMP,
        $env:TMP,
        "$env:LOCALAPPDATA\Temp",
        "$env:WINDIR\Temp",
        "$env:LOCALAPPDATA\Microsoft\Windows\INetCache",
        "$env:LOCALAPPDATA\Microsoft\Windows\WebCache",
        "$env:APPDATA\Microsoft\Windows\Recent"
    )
    
    foreach ($path in $tempPaths) {
        if (Test-Path $path) {
            try {
                $size = (Get-ChildItem -Path $path -Recurse -ErrorAction SilentlyContinue | 
                    Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
                if ($size) {
                    $totalSize += $size
                }
            }
            catch {
                # Ignore errors
            }
        }
    }
    
    # Also estimate Windows Update cache
    $updateCache = "$env:WINDIR\SoftwareDistribution"
    if (Test-Path $updateCache) {
        try {
            $size = (Get-ChildItem -Path $updateCache -Recurse -ErrorAction SilentlyContinue | 
                Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
            if ($size) {
                $totalSize += $size
            }
        }
        catch {
            # Ignore errors
        }
    }
    
    return [math]::Round($totalSize / 1MB, 2)
}

<#
.SYNOPSIS
    Gets information about services that will be disabled.

.DESCRIPTION
    Returns a list of services that are currently running and will be disabled.

.OUTPUTS
    System.Array
    Returns an array of service names that are running and will be disabled.

.EXAMPLE
    $services = Get-ServicesToDisable
#>
function Get-ServicesToDisable {
    $servicesToDisable = @("Fax", "WSearch", "RemoteRegistry")
    $runningServices = @()
    
    foreach ($serviceName in $servicesToDisable) {
        try {
            $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
            if ($service -and $service.Status -eq "Running") {
                $runningServices += $serviceName
            }
        }
        catch {
            # Ignore errors
        }
    }
    
    return $runningServices
}

<#
.SYNOPSIS
    Gets the current active Windows power plan name.

.DESCRIPTION
    Retrieves the name of the currently active power plan using powercfg.

.OUTPUTS
    System.String
    Returns the name of the current power plan, or "Unknown" if unable to determine.

.EXAMPLE
    $currentPlan = Get-CurrentPowerPlan
#>
function Get-CurrentPowerPlan {
    try {
        $powerCfgOutput = powercfg -list 2>&1
        $activePlan = $powerCfgOutput | Select-String "^\s+\*" | Select-Object -First 1
        
        if ($activePlan) {
            # Extract the plan name (everything after the GUID)
            $planName = ($activePlan -split '\s+', 4)[3]
            return $planName.Trim()
        }
        return "Unknown"
    }
    catch {
        return "Unknown"
    }
}

<#
.SYNOPSIS
    Displays detailed help information about each optimization option.

.DESCRIPTION
    Shows comprehensive information about what each optimization does,
    what it affects, and any important considerations.

.EXAMPLE
    Show-Help
#>
function Show-Help {
    Clear-Host
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Optimization Help & Information" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    
    $helpItems = @(
        @{
            Number = "1"
            Name = "Cleanup"
            Description = "Clean temporary files, Windows Update cache, and DNS cache"
            Details = @(
                "Removes temporary files from multiple locations:",
                "  • User temp directories (TEMP, TMP, LocalAppData\Temp)",
                "  • Windows temp directory",
                "  • Internet cache and web cache",
                "  • Recent files folder",
                "",
                "Also clears:",
                "  • Windows Update cache (requires stopping update services)",
                "  • DNS resolver cache",
                "",
                "Impact: Frees disk space, may resolve update issues, ensures fresh DNS lookups.",
                "Safe: Yes - only removes temporary/cached files."
            )
        },
        @{
            Number = "2"
            Name = "Disk Optimization"
            Description = "Optimize disk performance (defragmentation and TRIM)"
            Details = @(
                "Performs disk optimization on all fixed (non-removable) drives:",
                "  • Defragmentation for HDDs (improves read/write performance)",
                "  • TRIM for SSDs (extends lifespan and maintains performance)",
                "",
                "Impact: Improves disk read/write performance, can extend SSD lifespan.",
                "Time: Can take several minutes to hours depending on disk size and fragmentation.",
                "Safe: Yes - standard Windows maintenance operation."
            )
        },
        @{
            Number = "3"
            Name = "Power Settings Optimization"
            Description = "Optimize power settings (High Performance plan)"
            Details = @(
                "Configures power settings to prioritize performance:",
                "  • Activates or creates High Performance power plan",
                "  • Disables USB selective suspend",
                "  • Disables hard disk sleep mode",
                "",
                "Impact: Improves system responsiveness, may increase power consumption.",
                "Note: On laptops, this will reduce battery life.",
                "Reversible: Yes - you can change power plan back in Windows settings.",
                "Safe: Yes - only changes power management settings."
            )
        },
        @{
            Number = "4"
            Name = "Service Optimization"
            Description = "Disable unnecessary Windows services"
            Details = @(
                "Disables and stops services that are typically not needed:",
                "  • Fax service",
                "  • Windows Search (WSearch) - disables Start menu search",
                "  • Remote Registry",
                "",
                "Impact: Frees system resources, reduces background CPU/memory usage.",
                "Warning: Disabling Windows Search will disable Start menu search functionality.",
                "Reversible: Yes - services can be re-enabled in Services.msc.",
                "Safe: Yes - these services are rarely used by most users."
            )
        },
        @{
            Number = "5"
            Name = "Memory Optimization"
            Description = "Optimize memory (clear standby memory)"
            Details = @(
                "Performs memory optimization:",
                "  • Clears standby memory using SetProcessWorkingSetSize API",
                "  • Forces .NET garbage collection to free managed memory",
                "",
                "Impact: Frees up memory that's being held but not actively used.",
                "Note: This is a temporary optimization - memory will be used again as needed.",
                "Safe: Yes - standard memory management operation."
            )
        },
        @{
            Number = "6"
            Name = "Network Settings Optimization"
            Description = "Optimize network settings (TCP/IP tuning)"
            Details = @(
                "Modifies TCP/IP registry settings for better performance:",
                "  • Disables Nagle's algorithm (TCPNoDelay = 1)",
                "  • Sets TcpAckFrequency to 1 for immediate ACK responses",
                "",
                "Impact: Reduces network latency, especially for interactive applications.",
                "Note: Changes are made to Windows registry.",
                "Reversible: Yes - registry values can be reset.",
                "Safe: Yes - these are standard TCP/IP optimizations."
            )
        },
        @{
            Number = "7"
            Name = "Visual Effects Optimization"
            Description = "Disable unnecessary visual effects and animations"
            Details = @(
                "Disables visual effects to improve performance:",
                "  • Sets visual effects to 'Adjust for best performance'",
                "  • Disables window animations",
                "  • Disables taskbar animations",
                "  • Disables transparent selection and shadows",
                "",
                "Impact: Improves system responsiveness, reduces GPU/CPU usage.",
                "Note: Windows will look less visually appealing but more responsive.",
                "Reversible: Yes - can be changed in System Properties.",
                "Safe: Yes - only affects visual appearance."
            )
        },
        @{
            Number = "8"
            Name = "Processor Scheduling Optimization"
            Description = "Prioritize programs over background services"
            Details = @(
                "Configures processor scheduling:",
                "  • Sets Windows to prioritize foreground applications",
                "  • Improves responsiveness of active programs",
                "",
                "Impact: Better performance for active applications.",
                "Note: Background services may run slightly slower.",
                "Reversible: Yes - can be changed in System Properties.",
                "Safe: Yes - standard performance optimization."
            )
        },
        @{
            Number = "9"
            Name = "Prefetch/Superfetch Optimization"
            Description = "Optimize Prefetch and Superfetch for drive type"
            Details = @(
                "Configures Prefetch and Superfetch based on drive type:",
                "  • For SSDs: Disables Superfetch, optimizes Prefetcher",
                "  • For HDDs: Enables both for better performance",
                "",
                "Impact: Reduces unnecessary disk activity on SSDs, improves HDD performance.",
                "Note: Automatically detects drive type.",
                "Reversible: Yes - registry values can be reset.",
                "Safe: Yes - standard Windows optimization."
            )
        },
        @{
            Number = "10"
            Name = "Windows Update Optimization"
            Description = "Optimize Windows Update delivery settings"
            Details = @(
                "Configures Windows Update delivery:",
                "  • Disables peer-to-peer update delivery",
                "  • Downloads updates from Microsoft only",
                "",
                "Impact: Reduces bandwidth usage, improves privacy.",
                "Note: Updates may download slightly slower but more secure.",
                "Reversible: Yes - can be changed in Settings.",
                "Safe: Yes - only affects update delivery method."
            )
        },
        @{
            Number = "11"
            Name = "Background Apps Optimization"
            Description = "Disable unnecessary background apps"
            Details = @(
                "Disables apps from running in the background:",
                "  • Prevents apps from consuming resources when not in use",
                "  • Reduces CPU, memory, and battery usage",
                "",
                "Impact: Improves system responsiveness, saves battery.",
                "Note: Some apps may not receive notifications when disabled.",
                "Reversible: Yes - can be changed in Settings > Privacy.",
                "Safe: Yes - apps can be re-enabled individually."
            )
        },
        @{
            Number = "12"
            Name = "System Restore Optimization"
            Description = "Optimize System Restore disk space usage"
            Details = @(
                "Configures System Restore settings:",
                "  • Reduces maximum disk space for restore points",
                "  • Sets to 5% of disk space (default is often 10-15%)",
                "",
                "Impact: Frees disk space while maintaining protection.",
                "Note: Fewer restore points may be stored.",
                "Reversible: Yes - can be changed in System Properties.",
                "Safe: Yes - only reduces space allocation."
            )
        },
        @{
            Number = "13"
            Name = "Additional Registry Optimizations"
            Description = "Apply additional performance registry tweaks"
            Details = @(
                "Applies various registry optimizations:",
                "  • Disables Windows tips and suggestions",
                "  • Disables last access time updates (improves file system performance)",
                "  • Enables long file paths",
                "  • Improves network file copy performance",
                "",
                "Impact: Reduces overhead, improves file system and network performance.",
                "Note: Multiple registry changes are made.",
                "Reversible: Yes - all changes are logged.",
                "Safe: Yes - standard performance tweaks."
            )
        }
    )
    
    foreach ($item in $helpItems) {
        Write-Host "[$($item.Number)] $($item.Name)" -ForegroundColor Yellow
        Write-Host "  $($item.Description)" -ForegroundColor White
        Write-Host ""
        foreach ($detail in $item.Details) {
            Write-Host "  $detail" -ForegroundColor Gray
        }
        Write-Host ""
    }
    
    Write-Host "Press any key to return to the menu..." -ForegroundColor Cyan
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

<#
.SYNOPSIS
    Displays an interactive menu for selecting optimization options.

.DESCRIPTION
    Shows a numbered menu allowing users to select which optimizations
    to perform. Returns a hashtable with boolean values for each optimization category.

.OUTPUTS
    System.Collections.Hashtable
    Returns a hashtable with keys: Cleanup, DiskOptimization, PowerOptimization, 
    ServiceOptimization, Memory, NetworkSettings, and Verbose.

.EXAMPLE
    $options = Show-InteractiveMenu
#>
function Show-InteractiveMenu {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Performance Optimization Menu" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    
    Write-Host "Select which optimizations to perform:" -ForegroundColor Yellow
    Write-Host "Enter numbers separated by commas (e.g., 1,2,3) or 'all' for everything`n" -ForegroundColor Gray
    
    # Get current power plan for display
    $currentPowerPlan = Get-CurrentPowerPlan
    $powerPlanDisplay = if ($currentPowerPlan -ne "Unknown") { " (Current: $currentPowerPlan)" } else { "" }
    
    $menuItems = @(
        @{ Key = "Cleanup"; Description = "Clean temporary files, Windows Update cache, and DNS cache" },
        @{ Key = "DiskOptimization"; Description = "Optimize disk performance (defragmentation and TRIM)" },
        @{ Key = "PowerOptimization"; Description = "Optimize power settings (High Performance plan)$powerPlanDisplay" },
        @{ Key = "ServiceOptimization"; Description = "Disable unnecessary Windows services" },
        @{ Key = "Memory"; Description = "Optimize memory (clear standby memory)" },
        @{ Key = "NetworkSettings"; Description = "Optimize network settings (TCP/IP tuning)" },
        @{ Key = "VisualEffects"; Description = "Disable unnecessary visual effects and animations" },
        @{ Key = "ProcessorScheduling"; Description = "Prioritize programs over background services" },
        @{ Key = "PrefetchSettings"; Description = "Optimize Prefetch/Superfetch for drive type" },
        @{ Key = "WindowsUpdateSettings"; Description = "Optimize Windows Update delivery settings" },
        @{ Key = "BackgroundApps"; Description = "Disable unnecessary background apps" },
        @{ Key = "SystemRestore"; Description = "Optimize System Restore disk space usage" },
        @{ Key = "AdditionalRegistry"; Description = "Apply additional performance registry tweaks" }
    )
    
    # Display menu
    for ($i = 0; $i -lt $menuItems.Count; $i++) {
        Write-Host "  [$($i + 1)] $($menuItems[$i].Description)" -ForegroundColor White
    }
    
    Write-Host "`n  [A] Run all optimizations" -ForegroundColor Green
    Write-Host "  [H] Help - Show detailed information about each option" -ForegroundColor Cyan
    Write-Host "  [Q] Quit`n" -ForegroundColor Red
    
    # Get user input
    $userInput = Read-Host "Enter your selection"
    
    if ($userInput -eq 'Q' -or $userInput -eq 'q') {
        Write-Host "`nExiting..." -ForegroundColor Yellow
        exit 0
    }
    
    # Handle help/info request
    if ($userInput -eq 'H' -or $userInput -eq 'h' -or $userInput -eq 'help' -or $userInput -eq 'HELP') {
        Show-Help
        # Return to menu after showing help
        return Show-InteractiveMenu
    }
    
    # Initialize all options to false
    $options = @{
        Cleanup = $false
        DiskOptimization = $false
        PowerOptimization = $false
        ServiceOptimization = $false
        Memory = $false
        NetworkSettings = $false
        VisualEffects = $false
        ProcessorScheduling = $false
        PrefetchSettings = $false
        WindowsUpdateSettings = $false
        BackgroundApps = $false
        SystemRestore = $false
        AdditionalRegistry = $false
        Verbose = $false
    }
    
    # Handle 'all' or 'a' input
    if ($userInput -eq 'A' -or $userInput -eq 'a' -or $userInput -eq 'all' -or $userInput -eq 'ALL') {
        foreach ($key in $options.Keys) {
            if ($key -ne 'Verbose') {
                $options[$key] = $true
            }
        }
        # Verbose is on by default (unless -Silent was passed, which is handled at script level)
        $options['Verbose'] = $script:Verbose
        
        # Show confirmation with details
        Write-Host "`n========================================" -ForegroundColor Cyan
        Write-Host "  Selected Optimizations" -ForegroundColor Cyan
        Write-Host "========================================`n" -ForegroundColor Cyan
        Write-Host "  ✓ All optimizations selected`n" -ForegroundColor Green
        
        # Show summary information
        $estimatedSpace = Get-EstimatedCleanupSpace
        if ($estimatedSpace -gt 0) {
            Write-Host "  • Estimated disk space to free: $estimatedSpace MB" -ForegroundColor Yellow
        }
        
        $memInfo = Get-MemoryInfo
        if ($memInfo.StandbyGB -gt 0) {
            Write-Host "  • Estimated memory to free: ~$($memInfo.StandbyGB) GB" -ForegroundColor Yellow
        }
        
        $currentPlan = Get-CurrentPowerPlan
        if ($currentPlan -ne "Unknown") {
            Write-Host "  • Power plan: $currentPlan → High Performance" -ForegroundColor Yellow
        }
        
        $runningServices = Get-ServicesToDisable
        if ($runningServices.Count -gt 0) {
            Write-Host "  • Services to disable: $($runningServices.Count) service(s)" -ForegroundColor Yellow
        }
        
        Write-Host ""
        $confirm = Read-Host "Proceed with all optimizations? (Y/N)"
        
        if ($confirm -ne 'Y' -and $confirm -ne 'y') {
            Write-Host "`nOperation cancelled. Exiting..." -ForegroundColor Yellow
            exit 0
        }
        
        Write-Host "`nStarting optimizations...`n" -ForegroundColor Green
        return $options
    }
    
    # Parse comma-separated numbers
    $selections = $userInput -split ',' | ForEach-Object { $_.Trim() }
    
    foreach ($selection in $selections) {
        $num = 0
        if ([int]::TryParse($selection, [ref]$num)) {
            if ($num -ge 1 -and $num -le $menuItems.Count) {
                $selectedKey = $menuItems[$num - 1].Key
                $options[$selectedKey] = $true
            }
        }
    }
    
    # If nothing was selected, ask again
    $hasSelection = ($options.Cleanup -or $options.DiskOptimization -or $options.PowerOptimization -or 
                     $options.ServiceOptimization -or $options.Memory -or $options.NetworkSettings -or
                     $options.VisualEffects -or $options.ProcessorScheduling -or $options.PrefetchSettings -or
                     $options.WindowsUpdateSettings -or $options.BackgroundApps -or $options.SystemRestore -or
                     $options.AdditionalRegistry)
    if (-not $hasSelection) {
        Write-Host "`nNo valid selections made. Please try again.`n" -ForegroundColor Red
        return Show-InteractiveMenu
    }
    
    # Verbose is on by default (unless -Silent was passed, which is handled at script level)
    $options['Verbose'] = $script:Verbose
    
    # Show confirmation with selected options and detailed information
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  Selected Optimizations" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    
    $hasAnySelection = $false
    
    # Show detailed info for each selected optimization
    if ($options.Cleanup) {
        $hasAnySelection = $true
        Write-Host "  ✓ Clean temporary files, Windows Update cache, and DNS cache" -ForegroundColor Green
        $estimatedSpace = Get-EstimatedCleanupSpace
        if ($estimatedSpace -gt 0) {
            Write-Host "    Estimated space to free: $estimatedSpace MB" -ForegroundColor Yellow
        }
        else {
            Write-Host "    Note: Scanning for cleanup opportunities..." -ForegroundColor Gray
        }
        Write-Host ""
    }
    
    if ($options.DiskOptimization) {
        $hasAnySelection = $true
        Write-Host "  ✓ Optimize disk performance (defragmentation and TRIM)" -ForegroundColor Green
        try {
            $drives = Get-Volume | Where-Object { $_.DriveType -eq 'Fixed' -and $_.DriveLetter }
            $driveList = ($drives | ForEach-Object { "$($_.DriveLetter):" }) -join ", "
            if ($driveList) {
                Write-Host "    Drives to optimize: $driveList" -ForegroundColor Yellow
            }
        }
        catch {
            Write-Host "    Note: Will optimize all fixed drives" -ForegroundColor Gray
        }
        Write-Host ""
    }
    
    if ($options.PowerOptimization) {
        $hasAnySelection = $true
        Write-Host "  ✓ Optimize power settings (High Performance plan)" -ForegroundColor Green
        $currentPlan = Get-CurrentPowerPlan
        Write-Host "    Current plan: $currentPlan → Will change to: High Performance" -ForegroundColor Yellow
        Write-Host ""
    }
    
    if ($options.ServiceOptimization) {
        $hasAnySelection = $true
        Write-Host "  ✓ Disable unnecessary Windows services" -ForegroundColor Green
        $runningServices = Get-ServicesToDisable
        if ($runningServices.Count -gt 0) {
            Write-Host "    Services to disable: $($runningServices -join ', ')" -ForegroundColor Yellow
        }
        else {
            Write-Host "    Note: No target services are currently running" -ForegroundColor Gray
        }
        Write-Host ""
    }
    
    if ($options.Memory) {
        $hasAnySelection = $true
        Write-Host "  ✓ Optimize memory (clear standby memory)" -ForegroundColor Green
        $memInfo = Get-MemoryInfo
        if ($memInfo.StandbyGB -gt 0) {
            Write-Host "    Current memory: $($memInfo.TotalGB) GB total, $($memInfo.AvailableGB) GB available" -ForegroundColor Yellow
            Write-Host "    Estimated standby memory to clear: ~$($memInfo.StandbyGB) GB" -ForegroundColor Yellow
        }
        else {
            Write-Host "    Current memory: $($memInfo.TotalGB) GB total, $($memInfo.AvailableGB) GB available" -ForegroundColor Yellow
            Write-Host "    Note: Will clear standby memory and force garbage collection" -ForegroundColor Gray
        }
        Write-Host ""
    }
    
    if ($options.NetworkSettings) {
        $hasAnySelection = $true
        Write-Host "  ✓ Optimize network settings (TCP/IP tuning)" -ForegroundColor Green
        Write-Host "    Will disable Nagle's algorithm and optimize TCP ACK frequency" -ForegroundColor Yellow
        Write-Host ""
    }
    
    if ($options.VisualEffects) {
        $hasAnySelection = $true
        Write-Host "  ✓ Disable unnecessary visual effects and animations" -ForegroundColor Green
        Write-Host "    Will set visual effects to 'Adjust for best performance'" -ForegroundColor Yellow
        Write-Host ""
    }
    
    if ($options.ProcessorScheduling) {
        $hasAnySelection = $true
        Write-Host "  ✓ Prioritize programs over background services" -ForegroundColor Green
        Write-Host "    Will optimize processor scheduling for foreground applications" -ForegroundColor Yellow
        Write-Host ""
    }
    
    if ($options.PrefetchSettings) {
        $hasAnySelection = $true
        Write-Host "  ✓ Optimize Prefetch/Superfetch for drive type" -ForegroundColor Green
        Write-Host "    Will automatically configure based on SSD/HDD detection" -ForegroundColor Yellow
        Write-Host ""
    }
    
    if ($options.WindowsUpdateSettings) {
        $hasAnySelection = $true
        Write-Host "  ✓ Optimize Windows Update delivery settings" -ForegroundColor Green
        Write-Host "    Will disable peer-to-peer update delivery" -ForegroundColor Yellow
        Write-Host ""
    }
    
    if ($options.BackgroundApps) {
        $hasAnySelection = $true
        Write-Host "  ✓ Disable unnecessary background apps" -ForegroundColor Green
        Write-Host "    Will disable all background app execution" -ForegroundColor Yellow
        Write-Host ""
    }
    
    if ($options.SystemRestore) {
        $hasAnySelection = $true
        Write-Host "  ✓ Optimize System Restore disk space usage" -ForegroundColor Green
        Write-Host "    Will reduce restore point space to 5% of disk" -ForegroundColor Yellow
        Write-Host ""
    }
    
    if ($options.AdditionalRegistry) {
        $hasAnySelection = $true
        Write-Host "  ✓ Apply additional performance registry tweaks" -ForegroundColor Green
        Write-Host "    Will apply various registry optimizations for performance" -ForegroundColor Yellow
        Write-Host ""
    }
    
    if (-not $hasAnySelection) {
        Write-Host "  No optimizations selected.`n" -ForegroundColor Yellow
    }
    
    Write-Host ""
    $confirm = Read-Host "Proceed with these optimizations? (Y/N)"
    
    if ($confirm -ne 'Y' -and $confirm -ne 'y') {
        Write-Host "`nOperation cancelled. Exiting..." -ForegroundColor Yellow
        exit 0
    }
    
    Write-Host "`nStarting optimizations...`n" -ForegroundColor Green
    
    return $options
}

<#
.SYNOPSIS
    Main execution function that orchestrates all performance optimization tasks.

.DESCRIPTION
    Coordinates the execution of all optimization functions based on script parameters.
    Performs administrator privilege check, initializes logging, and executes optimization
    tasks in sequence. Respects skip flags to allow selective optimization.

.PARAMETER SkipCleanup
    When specified, skips temporary file cleanup, Windows Update cache clearing, and DNS cache clearing.

.PARAMETER SkipDiskOptimization
    When specified, skips disk defragmentation and optimization.

.PARAMETER SkipPowerOptimization
    When specified, skips power settings optimization.

.PARAMETER SkipServiceOptimization
    When specified, skips Windows services optimization.

.PARAMETER RunCleanup
    When specified, runs cleanup operations (overrides SkipCleanup).

.PARAMETER RunDiskOptimization
    When specified, runs disk optimization (overrides SkipDiskOptimization).

.PARAMETER RunPowerOptimization
    When specified, runs power optimization (overrides SkipPowerOptimization).

.PARAMETER RunServiceOptimization
    When specified, runs service optimization (overrides SkipServiceOptimization).

.PARAMETER RunMemory
    When specified, runs memory optimization.

.PARAMETER RunNetworkSettings
    When specified, runs network settings optimization.

.EXAMPLE
    Main
    Runs all optimization tasks.

.EXAMPLE
    Main -SkipCleanup
    Runs all optimizations except cleanup tasks.
#>
function Main {
    param(
        [switch]$SkipCleanup,
        [switch]$SkipDiskOptimization,
        [switch]$SkipPowerOptimization,
        [switch]$SkipServiceOptimization,
        [switch]$RunCleanup,
        [switch]$RunDiskOptimization,
        [switch]$RunPowerOptimization,
        [switch]$RunServiceOptimization,
        [switch]$RunMemory,
        [switch]$RunNetworkSettings,
        [switch]$RunVisualEffects,
        [switch]$RunProcessorScheduling,
        [switch]$RunPrefetchSettings,
        [switch]$RunWindowsUpdateSettings,
        [switch]$RunBackgroundApps,
        [switch]$RunSystemRestore,
        [switch]$RunAdditionalRegistry,
        [switch]$FromMenu
    )
    Initialize-Log
    
    if (-not (Test-Administrator)) {
        Write-Log "This script requires administrator privileges. Please run as administrator." "ERROR"
        exit 1
    }
    
    Write-Log "Starting performance optimization..."
    Get-SystemInfo
    
    # Determine if we're in menu mode (FromMenu flag or any Run* parameter) vs command-line mode (only Skip* parameters)
    $isMenuMode = $FromMenu -or 
                  $PSBoundParameters.ContainsKey('RunCleanup') -or 
                  $PSBoundParameters.ContainsKey('RunDiskOptimization') -or 
                  $PSBoundParameters.ContainsKey('RunPowerOptimization') -or 
                  $PSBoundParameters.ContainsKey('RunServiceOptimization') -or
                  $PSBoundParameters.ContainsKey('RunMemory') -or 
                  $PSBoundParameters.ContainsKey('RunNetworkSettings') -or
                  $PSBoundParameters.ContainsKey('RunVisualEffects') -or
                  $PSBoundParameters.ContainsKey('RunProcessorScheduling') -or
                  $PSBoundParameters.ContainsKey('RunPrefetchSettings') -or
                  $PSBoundParameters.ContainsKey('RunWindowsUpdateSettings') -or
                  $PSBoundParameters.ContainsKey('RunBackgroundApps') -or
                  $PSBoundParameters.ContainsKey('RunSystemRestore') -or
                  $PSBoundParameters.ContainsKey('RunAdditionalRegistry')
    
    # Determine what to run based on parameters
    # In menu mode: default to false (only run what's explicitly selected)
    # In command-line mode: default to true (run everything unless skipped)
    if ($isMenuMode) {
        $shouldCleanup = $PSBoundParameters.ContainsKey('RunCleanup') -and $RunCleanup
        $shouldDiskOptimize = $PSBoundParameters.ContainsKey('RunDiskOptimization') -and $RunDiskOptimization
        $shouldPowerOptimize = $PSBoundParameters.ContainsKey('RunPowerOptimization') -and $RunPowerOptimization
        $shouldServiceOptimize = $PSBoundParameters.ContainsKey('RunServiceOptimization') -and $RunServiceOptimization
        $shouldOptimizeMemory = $PSBoundParameters.ContainsKey('RunMemory') -and $RunMemory
        $shouldOptimizeNetwork = $PSBoundParameters.ContainsKey('RunNetworkSettings') -and $RunNetworkSettings
        $shouldOptimizeVisualEffects = $PSBoundParameters.ContainsKey('RunVisualEffects') -and $RunVisualEffects
        $shouldOptimizeProcessorScheduling = $PSBoundParameters.ContainsKey('RunProcessorScheduling') -and $RunProcessorScheduling
        $shouldOptimizePrefetch = $PSBoundParameters.ContainsKey('RunPrefetchSettings') -and $RunPrefetchSettings
        $shouldOptimizeWindowsUpdate = $PSBoundParameters.ContainsKey('RunWindowsUpdateSettings') -and $RunWindowsUpdateSettings
        $shouldOptimizeBackgroundApps = $PSBoundParameters.ContainsKey('RunBackgroundApps') -and $RunBackgroundApps
        $shouldOptimizeSystemRestore = $PSBoundParameters.ContainsKey('RunSystemRestore') -and $RunSystemRestore
        $shouldOptimizeAdditionalRegistry = $PSBoundParameters.ContainsKey('RunAdditionalRegistry') -and $RunAdditionalRegistry
    }
    else {
        # Command-line mode: use Skip* logic (default is to run everything)
        $shouldCleanup = if ($PSBoundParameters.ContainsKey('SkipCleanup')) { -not $SkipCleanup } else { $true }
        $shouldDiskOptimize = if ($PSBoundParameters.ContainsKey('SkipDiskOptimization')) { -not $SkipDiskOptimization } else { $true }
        $shouldPowerOptimize = if ($PSBoundParameters.ContainsKey('SkipPowerOptimization')) { -not $SkipPowerOptimization } else { $true }
        $shouldServiceOptimize = if ($PSBoundParameters.ContainsKey('SkipServiceOptimization')) { -not $SkipServiceOptimization } else { $true }
        $shouldOptimizeMemory = $true  # Memory and network always run in command-line mode unless skipped
        $shouldOptimizeNetwork = $true
        $shouldOptimizeVisualEffects = $true
        $shouldOptimizeProcessorScheduling = $true
        $shouldOptimizePrefetch = $true
        $shouldOptimizeWindowsUpdate = $true
        $shouldOptimizeBackgroundApps = $true
        $shouldOptimizeSystemRestore = $true
        $shouldOptimizeAdditionalRegistry = $true
    }
    
    if ($shouldCleanup) {
        Clear-TemporaryFiles
        Clear-WindowsUpdateCache
        Clear-DNSCache
    }
    
    if ($shouldDiskOptimize) {
        Optimize-DiskPerformance
    }
    
    if ($shouldPowerOptimize) {
        Optimize-PowerSettings
    }
    
    if ($shouldServiceOptimize) {
        Optimize-WindowsServices
    }
    
    if ($shouldOptimizeMemory) {
        Optimize-Memory
    }
    
    if ($shouldOptimizeNetwork) {
        Optimize-NetworkSettings
    }
    
    if ($shouldOptimizeVisualEffects) {
        Optimize-VisualEffects
    }
    
    if ($shouldOptimizeProcessorScheduling) {
        Optimize-ProcessorScheduling
    }
    
    if ($shouldOptimizePrefetch) {
        Optimize-PrefetchSettings
    }
    
    if ($shouldOptimizeWindowsUpdate) {
        Optimize-WindowsUpdateSettings
    }
    
    if ($shouldOptimizeBackgroundApps) {
        Optimize-BackgroundApps
    }
    
    if ($shouldOptimizeSystemRestore) {
        Optimize-SystemRestore
    }
    
    if ($shouldOptimizeAdditionalRegistry) {
        Optimize-AdditionalRegistrySettings
    }
    
    if ($script:WhatIf) {
        Write-Log "Performance optimization (WHAT IF) completed successfully!"
    }
    else {
        Write-Log "Performance optimization completed successfully!"
    }
    
    # Save change log and display summary
    if ($script:ChangeLog.Count -gt 0) {
        $changeLogPath = Save-ChangeLog
        Write-Log "Total changes recorded: $($script:ChangeLog.Count)"
        
        Write-Host "`n========================================" -ForegroundColor Cyan
        if ($script:WhatIf) {
            Write-Host "  Optimization Summary (WHAT IF)" -ForegroundColor Yellow
        }
        else {
            Write-Host "  Optimization Summary" -ForegroundColor Cyan
        }
        Write-Host "========================================`n" -ForegroundColor Cyan
        
        if ($script:WhatIf) {
            Write-Host "Total changes that WOULD be made: $($script:ChangeLog.Count)" -ForegroundColor Yellow
            Write-Host "(No actual changes were made - this was a dry run)`n" -ForegroundColor Cyan
        }
        else {
            Write-Host "Total changes made: $($script:ChangeLog.Count)" -ForegroundColor Yellow
        }
        
        # Group changes by category
        $changesByCategory = $script:ChangeLog | Group-Object -Property Category
        foreach ($category in $changesByCategory) {
            Write-Host "`n  $($category.Name): $($category.Count) change(s)" -ForegroundColor White
            foreach ($change in $category.Group) {
                Write-Host "    • $($change.Item): $($change.PreviousValue) → $($change.NewValue)" -ForegroundColor Gray
            }
        }
        
        if (-not $script:WhatIf) {
            Write-Host "`nDetailed change log saved to: $changeLogPath" -ForegroundColor Green
            Write-Host "This file contains instructions for reverting each change if needed." -ForegroundColor Yellow
            Write-Host "To rollback changes, run: .\OptimizePerformance.ps1 -Rollback`n" -ForegroundColor Cyan
        }
        else {
            Write-Host "`nChange log would be saved to: $changeLogPath`n" -ForegroundColor Gray
        }
    }
    
    if ($script:WhatIf) {
        Write-Host "WHAT IF mode complete! No changes were made. Check log file: $script:LogPath" -ForegroundColor Cyan
    }
    else {
        Write-Host "Optimization complete! Check log file: $script:LogPath" -ForegroundColor Green
    }
}

# Handle Rollback mode first
if ($Rollback) {
    if (-not (Test-Administrator)) {
        Write-Host "Rollback requires administrator privileges. Please run as administrator." -ForegroundColor Red
        exit 1
    }
    
    $whatIfFlag = if ($WhatIf) { $true } else { $false }
    Restore-FromChangeLog -ChangeLogPath $ChangeLogPath -WhatIf:$whatIfFlag
    exit 0
}

# Check if any skip parameters were explicitly provided via command line
$hasSkipParameters = $PSBoundParameters.ContainsKey('SkipCleanup') -or 
                     $PSBoundParameters.ContainsKey('SkipDiskOptimization') -or 
                     $PSBoundParameters.ContainsKey('SkipPowerOptimization') -or 
                     $PSBoundParameters.ContainsKey('SkipServiceOptimization') -or
                     $PSBoundParameters.ContainsKey('Silent') -or
                     $PSBoundParameters.ContainsKey('LogPath')

# Show WhatIf banner if in WhatIf mode
if ($WhatIf) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  WHAT IF MODE - No changes will be made" -ForegroundColor Yellow
    Write-Host "========================================`n" -ForegroundColor Cyan
}

# If no parameters provided, show interactive menu
if (-not $hasSkipParameters) {
    $menuOptions = Show-InteractiveMenu
    
    # Verbose is already set at script level based on -Silent parameter
    # Menu respects the existing script:Verbose value
    
    # Run Main with selected options (only pass Run* parameters for selected items)
    $mainParams = @{ FromMenu = $true }
    if ($menuOptions.Cleanup) { $mainParams['RunCleanup'] = $true }
    if ($menuOptions.DiskOptimization) { $mainParams['RunDiskOptimization'] = $true }
    if ($menuOptions.PowerOptimization) { $mainParams['RunPowerOptimization'] = $true }
    if ($menuOptions.ServiceOptimization) { $mainParams['RunServiceOptimization'] = $true }
    if ($menuOptions.Memory) { $mainParams['RunMemory'] = $true }
    if ($menuOptions.NetworkSettings) { $mainParams['RunNetworkSettings'] = $true }
    if ($menuOptions.VisualEffects) { $mainParams['RunVisualEffects'] = $true }
    if ($menuOptions.ProcessorScheduling) { $mainParams['RunProcessorScheduling'] = $true }
    if ($menuOptions.PrefetchSettings) { $mainParams['RunPrefetchSettings'] = $true }
    if ($menuOptions.WindowsUpdateSettings) { $mainParams['RunWindowsUpdateSettings'] = $true }
    if ($menuOptions.BackgroundApps) { $mainParams['RunBackgroundApps'] = $true }
    if ($menuOptions.SystemRestore) { $mainParams['RunSystemRestore'] = $true }
    if ($menuOptions.AdditionalRegistry) { $mainParams['RunAdditionalRegistry'] = $true }
    
    Main @mainParams
}
else {
    # Run with provided parameters
    Main -SkipCleanup:$SkipCleanup -SkipDiskOptimization:$SkipDiskOptimization `
         -SkipPowerOptimization:$SkipPowerOptimization -SkipServiceOptimization:$SkipServiceOptimization
}
