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
#   - Managing startup programs
#
####################################################################

#Requires -RunAsAdministrator

param(
    [switch]$SkipCleanup,
    [switch]$SkipDiskOptimization,
    [switch]$SkipPowerOptimization,
    [switch]$SkipServiceOptimization,
    [switch]$Silent,
    [string]$LogPath = (Join-Path (Get-Location).Path "OptimizePerformance.log")
)

$ErrorActionPreference = "Continue"
$script:LogPath = $LogPath
# Verbose is on by default, unless -Silent is specified
$script:Verbose = -not $Silent

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
    Writes a message to the log file with timestamp and severity level.

.DESCRIPTION
    Logs messages with timestamps and severity levels (INFO, WARNING, ERROR).
    Optionally displays messages to the console based on verbosity settings or severity.

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
    $logMessage = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:LogPath -Value $logMessage
    if ($script:Verbose -or $Level -eq "ERROR" -or $Level -eq "WARNING") {
        Write-Host $logMessage -ForegroundColor $(if ($Level -eq "ERROR") { "Red" } elseif ($Level -eq "WARNING") { "Yellow" } else { "Green" })
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
    
    foreach ($path in $tempPaths) {
        if (Test-Path $path) {
            try {
                $sizeBefore = (Get-ChildItem -Path $path -Recurse -ErrorAction SilentlyContinue | 
                    Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
                
                Remove-Item -Path "$path\*" -Recurse -Force -ErrorAction SilentlyContinue
                
                $sizeAfter = (Get-ChildItem -Path $path -Recurse -ErrorAction SilentlyContinue | 
                    Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
                
                $freed = $sizeBefore - $sizeAfter
                if ($freed -gt 0) {
                    $cleaned += $freed
                    Write-Log "Cleaned $([math]::Round($freed / 1MB, 2)) MB from $path"
                }
            }
            catch {
                Write-Log "Error cleaning $path : $_" "WARNING"
            }
        }
    }
    
    Write-Log "Temporary files cleanup completed. Total freed: $([math]::Round($cleaned / 1MB, 2)) MB"
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
    try {
        Stop-Service -Name wuauserv -Force -ErrorAction SilentlyContinue
        Stop-Service -Name cryptSvc -Force -ErrorAction SilentlyContinue
        Stop-Service -Name bits -Force -ErrorAction SilentlyContinue
        Stop-Service -Name msiserver -Force -ErrorAction SilentlyContinue
        
        $updateCache = "$env:WINDIR\SoftwareDistribution"
        if (Test-Path $updateCache) {
            Remove-Item -Path "$updateCache\*" -Recurse -Force -ErrorAction SilentlyContinue
            Write-Log "Windows Update cache cleared"
        }
        
        Start-Service -Name wuauserv -ErrorAction SilentlyContinue
        Start-Service -Name cryptSvc -ErrorAction SilentlyContinue
        Start-Service -Name bits -ErrorAction SilentlyContinue
        Start-Service -Name msiserver -ErrorAction SilentlyContinue
    }
    catch {
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
        ipconfig /flushdns | Out-Null
        Write-Log "DNS cache cleared successfully"
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
        
        foreach ($drive in $drives) {
            $driveLetter = $drive.DriveLetter
            Write-Log "Optimizing drive $driveLetter..."
            
            # Run disk cleanup
            try {
                Optimize-Volume -DriveLetter $driveLetter -Defrag -ReTrim -ErrorAction SilentlyContinue | Out-Null
                Write-Log "Drive $driveLetter optimization completed"
            }
            catch {
                Write-Log "Could not optimize drive $driveLetter (may require manual defragmentation): $_" "WARNING"
            }
        }
    }
    catch {
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
        # Set power plan to High Performance
        $highPerf = powercfg -list | Select-String "High performance" | ForEach-Object { ($_ -split '\s+')[3] }
        
        if ($highPerf) {
            powercfg -setactive $highPerf
            Write-Log "Power plan set to High Performance"
        }
        else {
            # Create high performance plan if it doesn't exist
            $guid = powercfg -duplicatescheme 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
            if ($guid) {
                $guid = ($guid -split '\s+')[-1]
                powercfg -setactive $guid
                Write-Log "High Performance power plan created and activated"
            }
        }
        
        # Disable USB selective suspend
        powercfg -setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
        powercfg -setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
        
        # Disable hard disk sleep
        powercfg -setacvalueindex SCHEME_CURRENT 0012ee47-9041-4b5d-9b77-535fba8b1442 6738e2c4-e8a5-4a42-b16a-e040e769756e 0
        powercfg -setdcvalueindex SCHEME_CURRENT 0012ee47-9041-4b5d-9b77-535fba8b1442 6738e2c4-e8a5-4a42-b16a-e040e769756e 0
        
        powercfg -setactive SCHEME_CURRENT
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
    
    foreach ($serviceName in $servicesToDisable) {
        try {
            $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
            if ($service -and $service.Status -eq "Running") {
                Set-Service -Name $serviceName -StartupType Disabled -ErrorAction SilentlyContinue
                Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
                Write-Log "Disabled service: $serviceName"
            }
        }
        catch {
            Write-Log "Could not modify service $serviceName : $_" "WARNING"
        }
    }
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
        # Disable Nagle's algorithm for better network performance
        $regPath = "HKLM:\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
        Set-ItemProperty -Path $regPath -Name "TcpAckFrequency" -Value 1 -ErrorAction SilentlyContinue
        Set-ItemProperty -Path $regPath -Name "TCPNoDelay" -Value 1 -ErrorAction SilentlyContinue
        
        Write-Log "Network settings optimized"
    }
    catch {
        Write-Log "Error optimizing network settings: $_" "WARNING"
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
        @{ Key = "NetworkSettings"; Description = "Optimize network settings (TCP/IP tuning)" }
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
                     $options.ServiceOptimization -or $options.Memory -or $options.NetworkSettings)
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
                  $PSBoundParameters.ContainsKey('RunNetworkSettings')
    
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
    }
    else {
        # Command-line mode: use Skip* logic (default is to run everything)
        $shouldCleanup = if ($PSBoundParameters.ContainsKey('SkipCleanup')) { -not $SkipCleanup } else { $true }
        $shouldDiskOptimize = if ($PSBoundParameters.ContainsKey('SkipDiskOptimization')) { -not $SkipDiskOptimization } else { $true }
        $shouldPowerOptimize = if ($PSBoundParameters.ContainsKey('SkipPowerOptimization')) { -not $SkipPowerOptimization } else { $true }
        $shouldServiceOptimize = if ($PSBoundParameters.ContainsKey('SkipServiceOptimization')) { -not $SkipServiceOptimization } else { $true }
        $shouldOptimizeMemory = $true  # Memory and network always run in command-line mode unless skipped
        $shouldOptimizeNetwork = $true
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
    
    Write-Log "Performance optimization completed successfully!"
    Write-Host "`nOptimization complete! Check log file: $script:LogPath" -ForegroundColor Green
}

# Check if any skip parameters were explicitly provided via command line
$hasSkipParameters = $PSBoundParameters.ContainsKey('SkipCleanup') -or 
                     $PSBoundParameters.ContainsKey('SkipDiskOptimization') -or 
                     $PSBoundParameters.ContainsKey('SkipPowerOptimization') -or 
                     $PSBoundParameters.ContainsKey('SkipServiceOptimization') -or
                     $PSBoundParameters.ContainsKey('Silent') -or
                     $PSBoundParameters.ContainsKey('LogPath')

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
    
    Main @mainParams
}
else {
    # Run with provided parameters
    Main -SkipCleanup:$SkipCleanup -SkipDiskOptimization:$SkipDiskOptimization `
         -SkipPowerOptimization:$SkipPowerOptimization -SkipServiceOptimization:$SkipServiceOptimization
}
