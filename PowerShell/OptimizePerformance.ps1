####################################################################
#   Scripted by Kristian Røste
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
    [switch]$Verbose,
    [string]$LogPath = (Join-Path (Get-Location).Path "OptimizePerformance.log")
)

$ErrorActionPreference = "Continue"
$script:LogPath = $LogPath
$script:Verbose = $Verbose

# Initialize log file
function Initialize-Log {
    if (!(Test-Path $script:LogPath)) {
        New-Item -Path $script:LogPath -ItemType File -Force | Out-Null
    }
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $script:LogPath -Value "`n========== Performance Optimization Started: $timestamp =========="
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMessage = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:LogPath -Value $logMessage
    if ($script:Verbose -or $Level -eq "ERROR" -or $Level -eq "WARNING") {
        Write-Host $logMessage -ForegroundColor $(if ($Level -eq "ERROR") { "Red" } elseif ($Level -eq "WARNING") { "Yellow" } else { "Green" })
    }
}

function Test-Administrator {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Clean temporary files and caches
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
                $files = Get-ChildItem -Path $path -Recurse -ErrorAction SilentlyContinue | Measure-Object
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

# Clear Windows Update cache
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

# Clear DNS cache
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

# Optimize disk performance
function Optimize-DiskPerformance {
    Write-Log "Starting disk optimization..."
    
    try {
        $drives = Get-Volume | Where-Object { $_.DriveType -eq 'Fixed' -and $_.DriveLetter }
        
        foreach ($drive in $drives) {
            $driveLetter = $drive.DriveLetter
            Write-Log "Optimizing drive $driveLetter..."
            
            # Run disk cleanup
            try {
                $result = Optimize-Volume -DriveLetter $driveLetter -Defrag -ReTrim -ErrorAction SilentlyContinue
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

# Optimize power settings for performance
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

# Optimize Windows services
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

# Optimize memory
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

# Optimize network settings
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

# Get system information
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

# Main execution
function Main {
    Initialize-Log
    
    if (-not (Test-Administrator)) {
        Write-Log "This script requires administrator privileges. Please run as administrator." "ERROR"
        exit 1
    }
    
    Write-Log "Starting performance optimization..."
    Get-SystemInfo
    
    if (-not $SkipCleanup) {
        Clear-TemporaryFiles
        Clear-WindowsUpdateCache
        Clear-DNSCache
    }
    
    if (-not $SkipDiskOptimization) {
        Optimize-DiskPerformance
    }
    
    if (-not $SkipPowerOptimization) {
        Optimize-PowerSettings
    }
    
    if (-not $SkipServiceOptimization) {
        Optimize-WindowsServices
    }
    
    Optimize-Memory
    Optimize-NetworkSettings
    
    Write-Log "Performance optimization completed successfully!"
    Write-Host "`nOptimization complete! Check log file: $script:LogPath" -ForegroundColor Green
}

# Run main function
Main
