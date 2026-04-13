#Requires -Version 5.1
<#
.SYNOPSIS
    Regression tests for KillHangingProcesses.ps1 (spawn isolated pwsh / Windows PowerShell children).
#>
$ErrorActionPreference = 'Stop'
$ScriptUnderTest = Join-Path $PSScriptRoot 'KillHangingProcesses.ps1'

function Invoke-KhpChild {
    param(
        [string]$PwshPath,
        [string[]]$ScriptArgs,
        [switch]$QuietStdErr
    )
    # Call operator + native exit code is simpler than Start-Process and allows stderr redirect for negative tests.
    if ($QuietStdErr) {
        $null = & $PwshPath -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $ScriptUnderTest @ScriptArgs 2>$null
    }
    else {
        $null = & $PwshPath -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $ScriptUnderTest @ScriptArgs
    }
    return $LASTEXITCODE
}

function Test-KhpParse {
    $errs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($ScriptUnderTest, [ref]$null, [ref]$errs)
    if ($errs.Count -gt 0) { throw ($errs | Out-String) }
}

$pwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue
$pwsh7 = if ($pwshCmd) { $pwshCmd.Source } else { $null }
$ps51 = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'

$runners = @()
if ($pwsh7) { $runners += @{ Name = 'PowerShell7'; Path = $pwsh7 } }
if (Test-Path -LiteralPath $ps51) { $runners += @{ Name = 'PowerShell51'; Path = $ps51 } }

if ($runners.Count -eq 0) { throw 'No pwsh.exe or powershell.exe found to run child tests.' }

$failures = [System.Collections.Generic.List[string]]::new()

foreach ($r in $runners) {
    $tag = $r.Name
    $exe = $r.Path

    Write-Host "`n=== $tag ===" -ForegroundColor Cyan

    try {
        Test-KhpParse
        Write-Host "[$tag] ParseFile: OK"
    }
    catch {
        $failures.Add("[$tag] ParseFile: $($_.Exception.Message)")
        continue
    }

    $code = Invoke-KhpChild -PwshPath $exe -ScriptArgs @()
    if ($code -ne 0) { $failures.Add("[$tag] Default args: expected exit 0, got $code") }
    else { Write-Host "[$tag] Default args exit 0: OK" }

    $code = Invoke-KhpChild -PwshPath $exe -ScriptArgs @('-Hours', '0') -QuietStdErr
    if ($code -eq 0) { $failures.Add("[$tag] -Hours 0: expected non-zero exit, got 0") }
    else { Write-Host "[$tag] -Hours 0 rejects (exit $code): OK" }

    $code = Invoke-KhpChild -PwshPath $exe -ScriptArgs @('-LogDir', '') -QuietStdErr
    if ($code -eq 0) { $failures.Add("[$tag] -LogDir '': expected non-zero exit, got 0") }
    else { Write-Host "[$tag] -LogDir empty rejects (exit $code): OK" }

    $logRoot = Join-Path $env:TEMP ("khptest_" + [guid]::NewGuid().ToString('n'))
    New-Item -ItemType Directory -Path $logRoot | Out-Null
    try {
        $code = Invoke-KhpChild -PwshPath $exe -ScriptArgs @(
            '-Application', 'ZZZNoSuchProcess999',
            '-LogDir', $logRoot,
            '-DebugLogging'
        )
        $log = Join-Path $logRoot 'KillHangingProcesses.log'
        if ($code -ne 0) { $failures.Add("[$tag] Debug no-kill: expected exit 0, got $code") }
        elseif (-not (Test-Path -LiteralPath $log)) { $failures.Add("[$tag] Debug no-kill: log missing") }
        else {
            $raw = Get-Content -LiteralPath $log -Raw
            if ($raw -notmatch 'No process to kill') { $failures.Add("[$tag] Debug no-kill: expected 'No process to kill' in log") }
            else { Write-Host "[$tag] DebugLogging + no matches: OK" }
        }
    }
    finally {
        Remove-Item -LiteralPath $logRoot -Recurse -Force -ErrorAction SilentlyContinue
    }

    $dir = Join-Path $env:TEMP ("khptest_" + [guid]::NewGuid().ToString('n'))
    New-Item -ItemType Directory -Path $dir | Out-Null
    try {
        $code = Invoke-KhpChild -PwshPath $exe -ScriptArgs @(
            '-Application', 'pwsh',
            '-Hours', '876000',
            '-LogDir', $dir,
            '-DryRun'
        )
        $log = Join-Path $dir 'KillHangingProcesses.log'
        $raw = if (Test-Path -LiteralPath $log) { Get-Content -LiteralPath $log -Raw } else { '' }
        if ($code -ne 0) { $failures.Add("[$tag] Huge hours: expected exit 0, got $code") }
        elseif ($raw -match 'DryRun:') { $failures.Add("[$tag] Huge hours: unexpected DryRun lines") }
        else { Write-Host "[$tag] Huge hours (no kills): OK" }
    }
    finally {
        Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
    }

    $dir = Join-Path $env:TEMP ("khptest_" + [guid]::NewGuid().ToString('n'))
    New-Item -ItemType Directory -Path $dir | Out-Null
    try {
        $code = Invoke-KhpChild -PwshPath $exe -ScriptArgs @(
            '-Application', 'pwsh',
            '-Hours', '1',
            '-LogDir', $dir,
            '-DryRun'
        )
        $log = Join-Path $dir 'KillHangingProcesses.log'
        if ($code -ne 0) { $failures.Add("[$tag] DryRun pwsh: expected exit 0, got $code") }
        elseif (-not (Test-Path -LiteralPath $log)) { $failures.Add("[$tag] DryRun pwsh: log missing") }
        else { Write-Host "[$tag] DryRun pwsh + log file: OK" }
    }
    finally {
        Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
    }

    $dir = Join-Path $env:TEMP ("khptest_" + [guid]::NewGuid().ToString('n'))
    New-Item -ItemType Directory -Path $dir | Out-Null
    try {
        # Comma-separated value is one argument -> [string[]] Application in the child
        $code = Invoke-KhpChild -PwshPath $exe -ScriptArgs @(
            '-Application', 'pwsh,pwsh',
            '-Hours', '1',
            '-LogDir', $dir,
            '-DryRun'
        )
        $logPath = Join-Path $dir 'KillHangingProcesses.log'
        if ($code -ne 0) { $failures.Add("[$tag] Dedupe child: expected exit 0, got $code") }
        elseif (-not (Test-Path -LiteralPath $logPath)) { $failures.Add("[$tag] Dedupe: log missing") }
        else {
            $lines = Get-Content -LiteralPath $logPath
            $dry = @($lines | Where-Object { $_ -match 'DryRun: would stop' })
            $ids = foreach ($l in $dry) { if ($l -match 'Id=(\d+)') { [int]$Matches[1] } }
            $dup = @($ids | Group-Object | Where-Object { $_.Count -gt 1 })
            if ($dup.Count -gt 0) { $failures.Add("[$tag] Dedupe: duplicate PIDs in log") }
            else { Write-Host "[$tag] Duplicate prefix dedupe: OK" }
        }
    }
    finally {
        Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
    }

    $dir = Join-Path $env:TEMP ("khptest_" + [guid]::NewGuid().ToString('n'))
    New-Item -ItemType Directory -Path $dir | Out-Null
    try {
        $code = Invoke-KhpChild -PwshPath $exe -ScriptArgs @(
            '-Application', 'ZZZNoSuchProcess999',
            '-Hours', '99',
            '-LogDir', $dir,
            '-DebugLogging'
        )
        $log = Join-Path $dir 'KillHangingProcesses.log'
        if ($code -ne 0) { $failures.Add("[$tag] Hours override child: expected exit 0, got $code") }
        elseif (-not (Test-Path -LiteralPath $log)) { $failures.Add("[$tag] Hours override: log missing (exit was 0)") }
        else {
            $raw = Get-Content -LiteralPath $log -Raw
            if ($raw -notmatch 'more than 99 hours') { $failures.Add("[$tag] -Hours override not reflected in debug log") }
            else { Write-Host "[$tag] -Hours parameter overrides default: OK" }
        }
    }
    finally {
        Remove-Item -LiteralPath $dir -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "`n========== SUMMARY ==========" -ForegroundColor Cyan
if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Host $_ -ForegroundColor Red }
    exit 1
}

Write-Host "All tests passed ($($runners.Count) runner(s))." -ForegroundColor Green
exit 0
