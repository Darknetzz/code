# --- Define the Action ---
# -Execute: The binary to run (e.g., php-cgi.exe, python.exe, or powershell.exe)
# -Argument: Flags and file paths. 
# -WorkingDirectory: Crucial for scripts that use relative paths (prevents System32 errors)
$Action = New-ScheduledTaskAction `
    -Execute "C:\Path\To\php.exe" `
    -Argument "-f C:\Scripts\worker.php" `
    -WorkingDirectory "C:\Scripts"

# --- Define the Trigger ---
# We start with a daily trigger, but add a RepetitionInterval.
# Other options for -At: "3am", "15:00", or $(Get-Date) for "starting now"
$Trigger = New-ScheduledTaskTrigger -Daily -At 12:00am

# Repetition options:
# -RepetitionInterval: '1 hour', '15 minutes', '12 hours'
# -RepetitionDuration: [TimeSpan]::MaxValue ensures it runs forever (Indefinitely)
$Trigger.RepetitionInterval = (New-TimeSpan -Hours 1)
$Trigger.RepetitionDuration = [TimeSpan]::MaxValue

# --- Define the Principal (Security Context) ---
# -UserId: "SYSTEM" (high priv), "LocalService", or "DOMAIN\User"
# -LogonType: 'ServiceAccount' (no password needed for SYSTEM) or 'Password' (needs -Password flag)
# -RunLevel: 'Highest' grants admin tokens (equivalent to sudo)
$Principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

# --- Define Settings (Optional but Recommended) ---
# -AllowStartIfOnBatteries: Good for laptops
# -DontStopIfGoingOnBatteries: Self-explanatory
# -ExecutionTimeLimit: Kill the task if it hangs (e.g., New-TimeSpan -Hours 2)
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# --- Register the Task ---
# Use -Force to overwrite an existing task with the same name (Idempotency!)
Register-ScheduledTask `
    -TaskName "HourlyPHPSync" `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Automated task running every hour to sync data" `
    -Force