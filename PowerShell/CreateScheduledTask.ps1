<#
.SYNOPSIS
    Creates a Windows Scheduled Task with configurable parameters.

.DESCRIPTION
    This script creates a scheduled task that can run repeatedly. It supports both
    interactive mode (prompts for missing values) and automated mode (all parameters provided).

.PARAMETER TaskName
    Name of the scheduled task. Required.

.PARAMETER Execute
    Path to the executable (e.g., php.exe, python.exe, powershell.exe). Required.

.PARAMETER Argument
    Arguments to pass to the executable. Optional.

.PARAMETER WorkingDirectory
    Working directory for the task. Optional but recommended for scripts using relative paths.

.PARAMETER TriggerTime
    Time to start the task (e.g., "12:00am", "3am", "15:00"). Defaults to "12:00am".

.PARAMETER RepetitionIntervalHours
    Hours between task repetitions. Set to 0 to disable repetition. Defaults to 1.

.PARAMETER RepetitionIntervalMinutes
    Minutes between task repetitions (used if RepetitionIntervalHours is 0). Defaults to 0.

.PARAMETER UserId
    User account to run the task as. Defaults to "SYSTEM".

.PARAMETER Password
    Password for the user account (required if LogonType is 'Password').

.PARAMETER LogonType
    Logon type: 'ServiceAccount' (no password) or 'Password'. Defaults to 'ServiceAccount'.

.PARAMETER RunLevel
    Run level: 'Highest' (admin) or 'Limited'. Defaults to 'Highest'.

.PARAMETER AllowStartIfOnBatteries
    Allow task to start on battery power. Defaults to $true.

.PARAMETER DontStopIfGoingOnBatteries
    Don't stop task when going on battery. Defaults to $true.

.PARAMETER ExecutionTimeLimitHours
    Maximum execution time in hours before task is killed. Defaults to 1.

.PARAMETER Description
    Description of the scheduled task. Optional.

.PARAMETER Force
    Overwrite existing task with the same name. Defaults to $true.

.EXAMPLE
    .\CreateScheduledTask.ps1 -TaskName "MyTask" -Execute "C:\Python\python.exe" -Argument "script.py"
    
.EXAMPLE
    .\CreateScheduledTask.ps1 -TaskName "HourlySync" -Execute "php.exe" -Argument "-f worker.php" -WorkingDirectory "C:\Scripts" -RepetitionIntervalHours 1
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$TaskName,
    
    [Parameter(Mandatory = $false)]
    [string]$Execute,
    
    [Parameter(Mandatory = $false)]
    [string]$Argument,
    
    [Parameter(Mandatory = $false)]
    [string]$WorkingDirectory,
    
    [Parameter(Mandatory = $false)]
    [string]$TriggerTime = "12:00am",
    
    [Parameter(Mandatory = $false)]
    [int]$RepetitionIntervalHours = 1,
    
    [Parameter(Mandatory = $false)]
    [int]$RepetitionIntervalMinutes = 0,
    
    [Parameter(Mandatory = $false)]
    [string]$UserId = "SYSTEM",
    
    [Parameter(Mandatory = $false)]
    [SecureString]$Password,
    
    [Parameter(Mandatory = $false)]
    [ValidateSet('ServiceAccount', 'Password')]
    [string]$LogonType = "ServiceAccount",
    
    [Parameter(Mandatory = $false)]
    [ValidateSet('Highest', 'Limited')]
    [string]$RunLevel = "Highest",
    
    [Parameter(Mandatory = $false)]
    [bool]$AllowStartIfOnBatteries = $true,
    
    [Parameter(Mandatory = $false)]
    [bool]$DontStopIfGoingOnBatteries = $true,
    
    [Parameter(Mandatory = $false)]
    [int]$ExecutionTimeLimitHours = 1,
    
    [Parameter(Mandatory = $false)]
    [string]$Description,
    
    [Parameter(Mandatory = $false)]
    [bool]$Force = $true
)

# Function to prompt for input if value is missing
function Get-RequiredParameter {
    param(
        [string]$ParameterName,
        [string]$Prompt,
        [string]$DefaultValue = $null
    )
    
    $value = Get-Variable -Name $ParameterName -ValueOnly -ErrorAction SilentlyContinue
    if ([string]::IsNullOrWhiteSpace($value)) {
        if ($DefaultValue) {
            $promptWithDefault = "${Prompt} (default: ${DefaultValue}): "
        } else {
            $promptWithDefault = "${Prompt}: "
        }
        $value = Read-Host -Prompt $promptWithDefault
        if ([string]::IsNullOrWhiteSpace($value) -and $DefaultValue) {
            $value = $DefaultValue
        }
    }
    return $value
}

# Function to prompt for secure password
function Get-PasswordInput {
    param([string]$Prompt)
    
    $securePassword = Read-Host -Prompt $Prompt -AsSecureString
    return $securePassword
}

# Interactive mode: Prompt for required parameters if not provided
if ([string]::IsNullOrWhiteSpace($TaskName)) {
    $TaskName = Get-RequiredParameter -ParameterName "TaskName" -Prompt "Enter task name"
}

if ([string]::IsNullOrWhiteSpace($Execute)) {
    $Execute = Get-RequiredParameter -ParameterName "Execute" -Prompt "Enter path to executable"
}

# Prompt for optional parameters if not provided (only in interactive mode)
if ([string]::IsNullOrWhiteSpace($Argument)) {
    $Argument = Read-Host -Prompt "Enter arguments (optional, press Enter to skip)"
}

if ([string]::IsNullOrWhiteSpace($WorkingDirectory)) {
    $WorkingDirectory = Read-Host -Prompt "Enter working directory (optional, press Enter to skip)"
}

if ([string]::IsNullOrWhiteSpace($Description)) {
    $Description = Read-Host -Prompt "Enter task description (optional, press Enter to skip)"
}

# Handle password if LogonType is Password
if ($LogonType -eq "Password" -and -not $Password) {
    $Password = Get-PasswordInput -Prompt "Enter password for user '$UserId'"
}

# --- Define the Action ---
$ActionParams = @{
    Execute = $Execute
}

if (-not [string]::IsNullOrWhiteSpace($Argument)) {
    $ActionParams['Argument'] = $Argument
}

if (-not [string]::IsNullOrWhiteSpace($WorkingDirectory)) {
    $ActionParams['WorkingDirectory'] = $WorkingDirectory
}

$Action = New-ScheduledTaskAction @ActionParams

# --- Define the Trigger ---
$Trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime

# Set repetition if interval is specified
if ($RepetitionIntervalHours -gt 0) {
    $Trigger.RepetitionInterval = New-TimeSpan -Hours $RepetitionIntervalHours
    $Trigger.RepetitionDuration = [TimeSpan]::MaxValue
} elseif ($RepetitionIntervalMinutes -gt 0) {
    $Trigger.RepetitionInterval = New-TimeSpan -Minutes $RepetitionIntervalMinutes
    $Trigger.RepetitionDuration = [TimeSpan]::MaxValue
}

# --- Define the Principal (Security Context) ---
$PrincipalParams = @{
    UserId = $UserId
    LogonType = $LogonType
    RunLevel = $RunLevel
}

if ($LogonType -eq "Password" -and $Password) {
    $PrincipalParams['Password'] = $Password
}

$Principal = New-ScheduledTaskPrincipal @PrincipalParams

# --- Define Settings ---
$SettingsParams = @{
    AllowStartIfOnBatteries = $AllowStartIfOnBatteries
    DontStopIfGoingOnBatteries = $DontStopIfGoingOnBatteries
    ExecutionTimeLimit = (New-TimeSpan -Hours $ExecutionTimeLimitHours)
}

$Settings = New-ScheduledTaskSettingsSet @SettingsParams

# --- Register the Task ---
$RegisterParams = @{
    TaskName = $TaskName
    Action = $Action
    Trigger = $Trigger
    Principal = $Principal
    Settings = $Settings
    Force = $Force
}

if (-not [string]::IsNullOrWhiteSpace($Description)) {
    $RegisterParams['Description'] = $Description
}

try {
    Register-ScheduledTask @RegisterParams
    Write-Host "Scheduled task '$TaskName' created successfully!" -ForegroundColor Green
} catch {
    Write-Error "Failed to create scheduled task: $_"
    exit 1
}