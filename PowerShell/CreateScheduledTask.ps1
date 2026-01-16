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
    User account to run the task as. Defaults to current user. Use "SYSTEM" for system account.

.PARAMETER Password
    Password for the user account (required if LogonType is 'Password').

.PARAMETER LogonType
    Logon type: 'ServiceAccount' (no password) or 'Password'. 
    Defaults to 'ServiceAccount' for SYSTEM/service accounts, 'Password' for regular users.

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
    [string]$UserId,
    
    [Parameter(Mandatory = $false)]
    [SecureString]$Password,
    
    [Parameter(Mandatory = $false)]
    [ValidateSet('ServiceAccount', 'Password')]
    [string]$LogonType,
    
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

# Function to check if running as administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Function to prompt for input if value is missing (with reprompting on empty input)
function Get-RequiredParameter {
    param(
        [string]$ParameterName,
        [string]$Prompt,
        [string]$DefaultValue = $null,
        [switch]$AllowEmpty = $false
    )
    
    $value = Get-Variable -Name $ParameterName -ValueOnly -ErrorAction SilentlyContinue
    
    # Keep prompting until we get a non-empty value (unless AllowEmpty is set)
    while ([string]::IsNullOrWhiteSpace($value)) {
        if ($DefaultValue) {
            $promptWithDefault = "${Prompt} (default: ${DefaultValue})"
        } else {
            $promptWithDefault = $Prompt
        }
        
        $inputValue = Read-Host -Prompt $promptWithDefault
        
        # If user entered something, use it
        if (-not [string]::IsNullOrWhiteSpace($inputValue)) {
            $value = $inputValue
        }
        # If user pressed Enter and there's a default, use it
        elseif ($DefaultValue) {
            $value = $DefaultValue
        }
        # If AllowEmpty is set, allow empty value
        elseif ($AllowEmpty) {
            return ""
        }
        # Otherwise, reprompt
        else {
            Write-Warning "This field is required. Please enter a value."
            continue
        }
    }
    
    return $value
}

# Function to prompt for credentials using Windows credential dialog
function Get-CredentialInput {
    param([string]$UserId)
    
    # Use Get-Credential to show Windows credential dialog
    # Pre-fill username if provided
    $credential = Get-Credential -Message "Enter credentials for the scheduled task" -UserName $UserId
    return $credential
}

# Check for administrator privileges at the beginning
if (-not (Test-Administrator)) {
    Write-Warning "This script requires administrator privileges to create scheduled tasks."
    Write-Warning "Please run PowerShell as Administrator and try again."
    exit 1
}

# Get current user for default UserId
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

# Interactive mode: Prompt for required parameters if not provided
if ([string]::IsNullOrWhiteSpace($TaskName)) {
    $TaskName = Get-RequiredParameter -ParameterName "TaskName" -Prompt "Enter task name"
}

if ([string]::IsNullOrWhiteSpace($Execute)) {
    $Execute = Get-RequiredParameter -ParameterName "Execute" -Prompt "Enter path to executable"
}

# Prompt for UserId if not provided (with current user as default)
if ([string]::IsNullOrWhiteSpace($UserId)) {
    $UserId = Get-RequiredParameter -ParameterName "UserId" -Prompt "Enter user account to run task as" -DefaultValue $currentUser
}

# Set LogonType default based on UserId
# SYSTEM and other service accounts use ServiceAccount, regular users need Password
if ([string]::IsNullOrWhiteSpace($LogonType)) {
    if ($UserId -eq "SYSTEM" -or $UserId -eq "NT AUTHORITY\SYSTEM" -or 
        $UserId -eq "LocalService" -or $UserId -eq "NT AUTHORITY\LocalService" -or
        $UserId -eq "NetworkService" -or $UserId -eq "NT AUTHORITY\NetworkService") {
        $LogonType = "ServiceAccount"
    } else {
        $LogonType = "Password"
    }
}

# Validate required parameters before proceeding
if ([string]::IsNullOrWhiteSpace($TaskName)) {
    Write-Error "Task name is required. Exiting." -ErrorAction Stop
    exit 1
}

if ([string]::IsNullOrWhiteSpace($Execute)) {
    Write-Error "Executable path is required. Exiting." -ErrorAction Stop
    exit 1
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
    $credential = Get-CredentialInput -UserId $UserId
    if ($credential) {
        # Update UserId if user entered a different username in credential dialog
        if ($credential.UserName -ne $UserId) {
            $UserId = $credential.UserName
            Write-Host "Using user account: $UserId" -ForegroundColor Yellow
        }
        # Extract password from credential
        $Password = $credential.Password
    } else {
        Write-Error "Credentials are required. Exiting." -ErrorAction Stop
        exit 1
    }
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
# Note: RepetitionInterval/RepetitionDuration only work with -Once triggers,
# so we create a temporary -Once trigger and copy its Repetition property
if ($RepetitionIntervalHours -gt 0 -or $RepetitionIntervalMinutes -gt 0) {
    $repetitionInterval = if ($RepetitionIntervalHours -gt 0) {
        New-TimeSpan -Hours $RepetitionIntervalHours
    } else {
        New-TimeSpan -Minutes $RepetitionIntervalMinutes
    }
    
    try {
        # Create a temporary trigger with -Once and repetition to get the Repetition object
        # Omit RepetitionDuration for indefinite repetition (more reliable than MaxValue)
        $tempTrigger = New-ScheduledTaskTrigger `
            -Once `
            -At "00:00" `
            -RepetitionInterval $repetitionInterval
        
        # Copy the Repetition property from temp trigger to daily trigger
        if ($tempTrigger.Repetition) {
            $Trigger.Repetition = $tempTrigger.Repetition
        } else {
            Write-Warning "Could not set repetition interval. Task will run once per day without repetition."
        }
    } catch {
        Write-Warning "Could not set repetition interval: $($_.Exception.Message)"
        Write-Warning "Task will run once per day without repetition."
    }
}

# --- Define the Principal (Security Context) ---
$PrincipalParams = @{
    UserId = $UserId
    LogonType = $LogonType
    RunLevel = $RunLevel
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
# When using password authentication, register with -User and -Password first,
# then update Principal settings separately to avoid parameter conflicts
if ($LogonType -eq "Password" -and $Password) {
    # Convert SecureString to plain text (required by Register-ScheduledTask)
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
    $plainPassword = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    
    # Create task object without Principal (we'll set it separately)
    $TaskParams = @{
        Action = $Action
        Trigger = $Trigger
        Settings = $Settings
    }
    
    if (-not [string]::IsNullOrWhiteSpace($Description)) {
        $TaskParams['Description'] = $Description
    }
    
    $Task = New-ScheduledTask @TaskParams
    
    # Register with -User and -Password (can't use -Principal here)
    $RegisterParams = @{
        TaskName = $TaskName
        InputObject = $Task
        User = $UserId
        Password = $plainPassword
        Force = $Force
    }
    
    try {
        Register-ScheduledTask @RegisterParams -ErrorAction Stop
        
        # Update Principal settings (RunLevel, etc.) after registration
        Set-ScheduledTask -TaskName $TaskName -Principal $Principal -ErrorAction Stop
        
        Write-Host "Scheduled task '$TaskName' created successfully!" -ForegroundColor Green
    } catch {
        $errorMessage = $_.Exception.Message
        
        # Check if task was actually created despite the error
        $taskExists = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($taskExists) {
            Write-Warning "Task registration reported an error, but the task '$TaskName' appears to have been created."
            Write-Warning "Error message: $errorMessage"
            Write-Host "Scheduled task '$TaskName' created successfully!" -ForegroundColor Green
        } else {
            # Task was not created, report the error
            if ($errorMessage -like "*Access is denied*") {
                Write-Error "Access denied. Please ensure you are running PowerShell as Administrator." -ErrorAction Stop
            } else {
                Write-Error "Failed to create scheduled task: $errorMessage" -ErrorAction Stop
            }
            exit 1
        }
    }
} else {
    # For ServiceAccount, we can use InputObject approach
    $TaskParams = @{
        Action = $Action
        Trigger = $Trigger
        Principal = $Principal
        Settings = $Settings
    }
    
    if (-not [string]::IsNullOrWhiteSpace($Description)) {
        $TaskParams['Description'] = $Description
    }
    
    $Task = New-ScheduledTask @TaskParams
    
    $RegisterParams = @{
        TaskName = $TaskName
        InputObject = $Task
        Force = $Force
    }
    
    try {
        Register-ScheduledTask @RegisterParams -ErrorAction Stop
        Write-Host "Scheduled task '$TaskName' created successfully!" -ForegroundColor Green
    } catch {
        $errorMessage = $_.Exception.Message
        
        # Check if task was actually created despite the error
        $taskExists = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($taskExists) {
            Write-Warning "Task registration reported an error, but the task '$TaskName' appears to have been created."
            Write-Warning "Error message: $errorMessage"
            Write-Host "Scheduled task '$TaskName' created successfully!" -ForegroundColor Green
        } else {
            # Task was not created, report the error
            if ($errorMessage -like "*Access is denied*") {
                Write-Error "Access denied. Please ensure you are running PowerShell as Administrator." -ErrorAction Stop
            } else {
                Write-Error "Failed to create scheduled task: $errorMessage" -ErrorAction Stop
            }
            exit 1
        }
    }
}