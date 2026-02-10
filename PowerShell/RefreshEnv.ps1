# Refresh environment variables in the current session from User and Machine (System).
# Run: . .\RefreshEnv.ps1   (dot-source so $env: updates apply in your session)

$keys = @(
    [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment'),
    [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('SYSTEM\CurrentControlSet\Control\Session Manager\Environment')
)
foreach ($key in $keys) {
    if (-not $key) { continue }
    try {
        foreach ($name in $key.GetValueNames()) {
            if ($name -eq 'Path') { continue }  # Path is handled below
            try {
                $val = $key.GetValue($name, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
                if ($null -ne $val) { [System.Environment]::SetEnvironmentVariable($name, $val, 'Process') }
            } catch {}
        }
    } finally {
        $key.Dispose()
    }
}

# Refresh Path in Process from User + Machine (append both)
$pathMachine = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
$pathUser    = [System.Environment]::GetEnvironmentVariable('Path', 'User')
# Prefer Machine + User order; if Process was already custom, this overwrites it with registry view
[System.Environment]::SetEnvironmentVariable('Path', ($pathMachine.TrimEnd(';') + ';' + $pathUser.TrimEnd(';')).Trim(';'), 'Process')

Write-Host 'Environment refreshed (User + Machine). Current session env vars updated.' -ForegroundColor Green
