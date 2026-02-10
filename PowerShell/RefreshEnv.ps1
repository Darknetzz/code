# Refresh environment variables in the current session from User and Machine (System).
# Run: . .\RefreshEnv.ps1   (dot-source so $env: updates apply in your session)

$locations = 'User', 'Machine'
foreach ($root in $locations) {
    $key = [Microsoft.Win32.Registry]::GetKey([Microsoft.Win32.RegistryHive]::$root, 'Environment')
    foreach ($name in $key.GetValueNames()) {
        if ($name -eq 'Path') { continue }  # Path is handled below
        try {
            $val = $key.GetValue($name, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
            if ($null -ne $val) { [System.Environment]::SetEnvironmentVariable($name, $val, 'Process') }
        } catch {}
    }
    $key.Dispose()
}

# Refresh Path in Process from User + Machine (append both)
$pathMachine = [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
$pathUser    = [System.Environment]::GetEnvironmentVariable('Path', 'User')
# Overwrite Process Path with Machine + User (registry view); any process-only Path is discarded
[System.Environment]::SetEnvironmentVariable('Path', ($pathMachine.TrimEnd(';') + ';' + $pathUser.TrimEnd(';')).Trim(';'), 'Process')

Write-Host 'Environment refreshed (User + Machine). Current session env vars updated.' -ForegroundColor Green
