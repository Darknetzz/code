<#
.SYNOPSIS
    Configures a local user account for use as a service account (admin, RDP, log on as service).

.DESCRIPTION
    Performs up to three configurations for the specified user:
    1. Adds the user to the local Administrators group.
    2. Adds the user to the Remote Desktop Users group (allows RDP logon).
    3. Grants the user right "Log on as a service" (SeServiceLogonRight).

    By default, prompts before each step. Use -SetAsAdmin, -AllowRDP, and -AllowLogonAsService
    to predefine choices (no prompts for those steps). Use -All to apply all three without prompting.

    Requires elevation (Run as Administrator).

.PARAMETER UserName
    Name of the local user account to configure (e.g., DOMAIN\UserName or .\UserName for local).
    For local users, .\UserName or just UserName can be used.

.PARAMETER SetAsAdmin
    Add user to local Administrators. $true = do it, $false = skip. If not specified, prompts.

.PARAMETER AllowRDP
    Add user to Remote Desktop Users. $true = do it, $false = skip. If not specified, prompts.

.PARAMETER AllowLogonAsService
    Grant "Log on as a service". $true = do it, $false = skip. If not specified, prompts.

.PARAMETER All
    Apply all three configurations without prompting (equivalent to -SetAsAdmin -AllowRDP -AllowLogonAsService).

.EXAMPLE
    .\InstallServiceAccount.ps1 -UserName ".\MyServiceAccount"
    Prompts for each step.
.EXAMPLE
    .\InstallServiceAccount.ps1 -UserName ".\svc" -All
    Applies admin, RDP, and logon-as-service without prompts.
.EXAMPLE
    .\InstallServiceAccount.ps1 -UserName ".\svc" -SetAsAdmin -AllowRDP
    Adds to Administrators and Remote Desktop Users; prompts only for "Log on as a service".
.EXAMPLE
    .\InstallServiceAccount.ps1 -UserName "DOMAIN\svc_app" -SetAsAdmin -AllowLogonAsService -AllowRDP:$false
    Admin and logon-as-service only; skips RDP.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$UserName,

    [Parameter()]
    [Nullable[bool]]$SetAsAdmin = $null,

    [Parameter()]
    [Nullable[bool]]$AllowRDP = $null,

    [Parameter()]
    [Nullable[bool]]$AllowLogonAsService = $null,

    [Parameter()]
    [switch]$All
)

#Requires -RunAsAdministrator

$ErrorActionPreference = 'Stop'

function Get-StepChoice {
    param([Nullable[bool]]$Override, [string]$Prompt)
    if ($null -ne $Override) { return [bool]$Override }
    $response = Read-Host $Prompt
    return ($response -eq '' -or $response -match '^y(es)?$')
}

function Add-UserToLocalGroup {
    param([string]$GroupName, [string]$Member)
    if (Get-LocalGroupMember -Group $GroupName -Member $Member -ErrorAction SilentlyContinue) {
        Write-Verbose "User '$Member' is already in '$GroupName'."
        return
    }
    Add-LocalGroupMember -Group $GroupName -Member $Member
    Write-Host "Added '$Member' to local group '$GroupName'."
}

function Grant-SeServiceLogonRight {
    param([string]$AccountName)
    $sid = (New-Object System.Security.Principal.NTAccount($AccountName)).Translate([System.Security.Principal.SecurityIdentifier])
    $sidValue = $sid.Value
    $rightName = 'SeServiceLogonRight'
    $tempCfg = [System.IO.Path]::GetTempPath() + [Guid]::NewGuid().ToString() + '.inf'
    try {
        & secedit /export /cfg $tempCfg /areas USER_RIGHTS | Out-Null
        $content = Get-Content $tempCfg -Raw
        if ($content -match "(\[Privilege Rights\][\s\S]*?)($rightName\s*=\s*)([^\r\n]*)") {
            $rightLine = $Matches[2] + $Matches[3]
            if ($rightLine -match [regex]::Escape("*$sidValue")) {
                Write-Verbose "User '$AccountName' already has '$rightName'."
                return
            }
            $newRightLine = $rightLine.TrimEnd() + ",*$sidValue"
            $content = $content -replace [regex]::Escape($rightLine), $newRightLine
            Set-Content -Path $tempCfg -Value $content -NoNewline
            $sysDb = Join-Path $env:windir 'security\database\secedit.sdb'
            & secedit /configure /db $sysDb /cfg $tempCfg /areas USER_RIGHTS | Out-Null
            Write-Host "Granted '$rightName' to '$AccountName'."
        } else {
            throw "Could not find $rightName in exported security policy."
        }
    } finally {
        if (Test-Path $tempCfg) { Remove-Item $tempCfg -Force }
    }
}

# Normalize .\UserName to local machine name for consistency
if ($UserName -match '^\.\\(.+)$') {
    $UserName = "$env:COMPUTERNAME\$($Matches[1])"
}

if ($All) {
    $SetAsAdmin = $true
    $AllowRDP = $true
    $AllowLogonAsService = $true
}

Write-Host "Configuring service account: $UserName"

$doAdmin = Get-StepChoice -Override $SetAsAdmin -Prompt "Add $UserName to local Administrators? (Y/n)"
if ($doAdmin) { Add-UserToLocalGroup -GroupName 'Administrators' -Member $UserName }

$doRdp = Get-StepChoice -Override $AllowRDP -Prompt "Add $UserName to Remote Desktop Users (allow RDP)? (Y/n)"
if ($doRdp) { Add-UserToLocalGroup -GroupName 'Remote Desktop Users' -Member $UserName }

$doService = Get-StepChoice -Override $AllowLogonAsService -Prompt "Grant $UserName 'Log on as a service'? (Y/n)"
if ($doService) { Grant-SeServiceLogonRight -AccountName $UserName }

Write-Host "Done."
