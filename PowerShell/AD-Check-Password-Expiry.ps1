<#
.SYNOPSIS
    Shows Active Directory password expiry and last-set information for a user.

.DESCRIPTION
    Looks up a domain user and reports when the password was last set, when it
    expires (if applicable), and related password flags.

.PARAMETER UserName
    sAMAccountName or UPN of the user. If omitted, you are prompted.

.EXAMPLE
    .\AD-Check-Password-Expiry.ps1 jsmith
.EXAMPLE
    .\AD-Check-Password-Expiry.ps1 -UserName jsmith@contoso.com
.EXAMPLE
    .\AD-Check-Password-Expiry.ps1
    Prompts for a username.
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string] $UserName
)

$ErrorActionPreference = 'Stop'

function Convert-FileTime([object] $FileTime) {
    if ($null -eq $FileTime -or [long] $FileTime -le 0) {
        return $null
    }
    return [datetime]::FromFileTime([long] $FileTime)
}

if (-not (Get-Module -ListAvailable -Name ActiveDirectory)) {
    throw 'ActiveDirectory module not found. Install RSAT Active Directory tools.'
}

Import-Module ActiveDirectory -ErrorAction Stop

if ([string]::IsNullOrWhiteSpace($UserName)) {
    $UserName = Read-Host 'Enter username (sAMAccountName or UPN)'
}

if ([string]::IsNullOrWhiteSpace($UserName)) {
    throw 'Username is required.'
}

$properties = @(
    'DisplayName',
    'SamAccountName',
    'UserPrincipalName',
    'Enabled',
    'pwdLastSet',
    'PasswordNeverExpires',
    'PasswordExpired',
    'msDS-UserPasswordExpiryTimeComputed'
)

$user = Get-ADUser -Identity $UserName -Properties $properties -ErrorAction Stop

$mustChangeAtLogon = [long] $user.pwdLastSet -eq 0
$passwordLastSet = if ($mustChangeAtLogon) { 'Must change at next logon' } else { Convert-FileTime $user.pwdLastSet }
$passwordExpires = Convert-FileTime $user.'msDS-UserPasswordExpiryTimeComputed'

$daysUntilExpiry = $null
if ($passwordExpires) {
    $daysUntilExpiry = [math]::Round(($passwordExpires - (Get-Date)).TotalDays, 1)
}

$passwordExpiresDisplay = if ($user.PasswordNeverExpires) {
    'Never (PasswordNeverExpires)'
} elseif ($mustChangeAtLogon) {
    'N/A (must change at next logon)'
} elseif ($passwordExpires) {
    $passwordExpires
} else {
    $null
}

$result = [PSCustomObject]@{
    SamAccountName       = $user.SamAccountName
    DisplayName          = $user.DisplayName
    UserPrincipalName    = $user.UserPrincipalName
    Enabled              = $user.Enabled
    PasswordLastSet      = $passwordLastSet
    PasswordExpires      = $passwordExpiresDisplay
    DaysUntilExpiry      = if ($user.PasswordNeverExpires -or $mustChangeAtLogon) { 'N/A' } else { $daysUntilExpiry }
    PasswordNeverExpires = $user.PasswordNeverExpires
    PasswordExpired      = $user.PasswordExpired
}

$result | Format-List
