<#
.SYNOPSIS
    Lists or exports the Active Directory groups a user belongs to.

.DESCRIPTION
    Domain Active Directory only (RSAT ActiveDirectory module).

    With no parameters, prompts for list vs export and the values that action
    needs. Wildcards * and ? are allowed in -UserName and -GroupName.

    The default action lists the user's direct groups, including the primary
    group. -Recursive also includes groups the user reaches through nesting.
    -GroupName filters that list by group name or sAMAccountName.
    -CsvPath or -Export writes the same rows to CSV.

    When several users match and -AllMatchingUsers is not set, matching users
    are shown and you are prompted to pick.

    Membership tests stay in AD-Group.ps1.

.PARAMETER UserName
    sAMAccountName, UPN, or display name. Wildcards * and ? are allowed.
    If omitted, you are prompted.

.PARAMETER GroupName
    Optional filter on group name or sAMAccountName. Wildcards * and ? are allowed.

.PARAMETER Recursive
    Include groups reached through nesting, not only direct membership.

.PARAMETER Export
    Write the group listing to CSV. Prompts for a path when -CsvPath is omitted.

.PARAMETER CsvPath
    CSV file to write. Parent folder must already exist. Implies export.

.PARAMETER AllMatchingUsers
    Process every user that matches -UserName instead of prompting.

.EXAMPLE
    .\AD-User.ps1
    Prompts for the action and any missing values.

.EXAMPLE
    .\AD-User.ps1 -UserName 'kriss'

.EXAMPLE
    .\AD-User.ps1 -UserName 'kriss' -Recursive

.EXAMPLE
    .\AD-User.ps1 -UserName 'kriss' -GroupName '*admin*'

.EXAMPLE
    .\AD-User.ps1 -UserName 'kr*'
    Prompts when more than one user matches.

.EXAMPLE
    .\AD-User.ps1 -UserName 'kr*' -AllMatchingUsers

.EXAMPLE
    .\AD-User.ps1 -UserName 'kriss' -CsvPath '.\groups.csv'

.EXAMPLE
    .\AD-User.ps1 -UserName 'kriss' -Export
    Prompts for the CSV path.

.NOTES
    Requires the ActiveDirectory module (RSAT) and a reachable domain controller.
    Both are checked before any prompt or lookup.
#>

[CmdletBinding(DefaultParameterSetName = 'Interactive')]
param(
    [Parameter(ParameterSetName = 'List', Position = 0)]
    [string] $UserName,

    [Parameter(ParameterSetName = 'List', Position = 1)]
    [string] $GroupName,

    [Parameter(ParameterSetName = 'List')]
    [switch] $Recursive,

    [Parameter(ParameterSetName = 'List')]
    [switch] $Export,

    [Parameter(ParameterSetName = 'List')]
    [string] $CsvPath,

    [Parameter(ParameterSetName = 'List')]
    [switch] $AllMatchingUsers
)

$ErrorActionPreference = 'Stop'

$script:UserGroupTypeName = 'Code.ADUserGroup'
$script:GroupProperties = @('Description', 'GroupCategory', 'GroupScope')

function ConvertTo-ADFilterLiteral {
    param([string] $Value)
    return $Value.Replace("'", "''")
}

function ConvertTo-LdapFilterLiteral {
    param([string] $Value)
    return ($Value.Replace('\', '\5c').Replace('*', '\2a').Replace('(', '\28').Replace(')', '\29').Replace("`0", '\00'))
}

function Test-WildcardPattern {
    param([string] $Value)
    return $Value.Contains('*') -or $Value.Contains('?')
}

function Test-ADIdentityNotFound {
    param($ErrorRecord)
    $exception = $ErrorRecord.Exception
    while ($exception) {
        if ($exception.GetType().Name -eq 'ADIdentityNotFoundException') {
            return $true
        }
        $exception = $exception.InnerException
    }
    return $ErrorRecord.CategoryInfo.Category -eq [System.Management.Automation.ErrorCategory]::ObjectNotFound
}

function Initialize-ActiveDirectoryModule {
    if (-not (Get-Module -ListAvailable -Name ActiveDirectory)) {
        throw 'ActiveDirectory module not found. Install RSAT Active Directory tools.'
    }

    try {
        Import-Module ActiveDirectory -ErrorAction Stop
    }
    catch {
        throw "ActiveDirectory module failed to load. $($_.Exception.Message)"
    }

    try {
        $null = Get-ADDomain -ErrorAction Stop
    }
    catch {
        throw "Cannot reach a domain controller. Confirm this computer is domain-joined, a DC is reachable, and Active Directory Web Services is running. $($_.Exception.Message)"
    }
}

function Read-HostText {
    param(
        [Parameter(Mandatory)]
        [string] $Prompt,

        [string] $Default,

        [switch] $Required
    )

    if ($Required -and -not [Environment]::UserInteractive) {
        throw "'$Prompt' is required. Pass it as a parameter when running non-interactively."
    }

    $label = if ($PSBoundParameters.ContainsKey('Default')) { "$Prompt [$Default]" } else { $Prompt }
    $value = Read-Host $label
    if ([string]::IsNullOrWhiteSpace($value)) {
        if ($PSBoundParameters.ContainsKey('Default')) {
            return $Default
        }
        if ($Required) {
            throw "'$Prompt' is required."
        }
        return ''
    }
    return $value.Trim()
}

function Read-YesNo {
    param(
        [Parameter(Mandatory)]
        [string] $Prompt,

        [bool] $Default = $false
    )

    $hint = if ($Default) { 'Y/n' } else { 'y/N' }
    $answer = Read-HostText -Prompt "$Prompt ($hint)" -Default $(if ($Default) { 'Y' } else { 'N' })
    return $answer -match '^(y|yes)$'
}

function Register-UserGroupDisplay {
    if (Get-TypeData -TypeName $script:UserGroupTypeName) {
        return
    }
    Update-TypeData -TypeName $script:UserGroupTypeName -DefaultDisplayPropertySet @(
        'User', 'Name', 'SamAccountName', 'GroupScope'
    ) -Force
}

function Get-ADUserByLike {
    param([string] $Name)

    $pattern = ConvertTo-ADFilterLiteral $Name
    $filter = "SamAccountName -like '$pattern' -or UserPrincipalName -like '$pattern' -or DisplayName -like '$pattern'"
    $properties = @('DisplayName', 'UserPrincipalName', 'Enabled', 'PrimaryGroup')
    return @(Get-ADUser -Filter $filter -Properties $properties | Where-Object { $_ })
}

function Resolve-ADUsers {
    param([Parameter(Mandatory)][string] $Name)

    if (Test-WildcardPattern $Name) {
        return @(Get-ADUserByLike -Name $Name)
    }

    $properties = @('DisplayName', 'UserPrincipalName', 'Enabled', 'PrimaryGroup')
    try {
        return @(Get-ADUser -Identity $Name -Properties $properties -ErrorAction Stop | Where-Object { $_ })
    }
    catch {
        if (-not (Test-ADIdentityNotFound $_)) { throw }
    }

    return @(Get-ADUserByLike -Name $Name)
}

function Select-ADUser {
    param(
        [Parameter(Mandatory)]
        $Users,

        [switch] $AllMatches
    )

    $matched = @($Users | Where-Object { $_ })
    if ($matched.Count -eq 0) {
        throw "No users matched '$UserName'."
    }
    if ($matched.Count -eq 1 -or $AllMatches) {
        return $matched
    }

    if (-not [Environment]::UserInteractive) {
        throw "Multiple users matched '$UserName'. Pass -AllMatchingUsers or a more specific -UserName."
    }

    $index = 1
    $summary = foreach ($user in $matched) {
        [PSCustomObject]@{
            Index          = $index
            Name           = $user.Name
            SamAccountName = $user.SamAccountName
            DisplayName    = $user.DisplayName
            Enabled        = $user.Enabled
        }
        $index++
    }
    $summary | Format-Table -AutoSize | Out-Host

    $answer = Read-HostText -Prompt "Multiple users matched. Enter a number, comma-separated numbers, or 'all'" -Required
    if ($answer -eq 'all') {
        return $matched
    }

    $seen = @{}
    $picked = foreach ($part in ($answer -split '[,\s]+' | Where-Object { $_ })) {
        $number = 0
        if (-not [int]::TryParse($part, [ref]$number) -or $number -lt 1 -or $number -gt $matched.Count) {
            throw "Invalid selection '$part'."
        }
        $user = $matched[$number - 1]
        if ($seen.ContainsKey($user.DistinguishedName)) {
            continue
        }
        $seen[$user.DistinguishedName] = $true
        $user
    }

    $picked = @($picked | Where-Object { $_ })
    if ($picked.Count -eq 0) {
        throw 'No users selected.'
    }
    return $picked
}

function Get-ADGroupMap {
    param([string[]] $DistinguishedNames)

    $map = @{}
    $names = @($DistinguishedNames | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($names.Count -eq 0) {
        return $map
    }

    $chunkSize = 25
    for ($offset = 0; $offset -lt $names.Count; $offset += $chunkSize) {
        $end = [Math]::Min($offset + $chunkSize - 1, $names.Count - 1)
        $chunk = @($names[$offset..$end])
        $filter = @(foreach ($dn in $chunk) {
                "DistinguishedName -eq '$(ConvertTo-ADFilterLiteral $dn)'"
            }) -join ' -or '

        foreach ($group in (Get-ADGroup -Filter $filter -Properties $script:GroupProperties)) {
            $map[$group.DistinguishedName] = $group
        }
    }

    return $map
}

function Add-GroupOnce {
    param(
        $Map,
        $Group
    )

    if (-not $Group -or -not $Group.DistinguishedName) {
        return
    }
    if (-not $Map.ContainsKey($Group.DistinguishedName)) {
        $Map[$Group.DistinguishedName] = $Group
    }
}

function Get-UserGroups {
    param(
        $User,
        [bool] $Recurse
    )

    $map = @{}
    if ($Recurse) {
        $escapedDn = ConvertTo-LdapFilterLiteral $User.DistinguishedName
        $ldapFilter = "(member:1.2.840.113556.1.4.1941:=$escapedDn)"
        foreach ($group in (Get-ADGroup -LDAPFilter $ldapFilter -Properties $script:GroupProperties)) {
            Add-GroupOnce -Map $map -Group $group
        }
    }
    else {
        $direct = @(Get-ADPrincipalGroupMembership -Identity $User.DistinguishedName)
        $resolved = Get-ADGroupMap -DistinguishedNames @($direct.DistinguishedName)
        foreach ($group in $resolved.Values) {
            Add-GroupOnce -Map $map -Group $group
        }
    }

    if ($User.PrimaryGroup -and -not $map.ContainsKey($User.PrimaryGroup)) {
        $primary = Get-ADGroup -Identity $User.PrimaryGroup -Properties $script:GroupProperties -ErrorAction Stop
        Add-GroupOnce -Map $map -Group $primary
    }

    return @($map.Values)
}

function Test-GroupNameLike {
    param(
        $Group,
        [string] $Pattern
    )

    if ([string]::IsNullOrWhiteSpace($Pattern)) {
        return $true
    }
    return ($Group.Name -like $Pattern) -or ($Group.SamAccountName -like $Pattern)
}

function New-UserGroupRow {
    param(
        $User,
        $Group
    )

    return [PSCustomObject]@{
        PSTypeName     = $script:UserGroupTypeName
        User           = $User.SamAccountName
        Name           = $Group.Name
        SamAccountName = $Group.SamAccountName
        GroupCategory  = $Group.GroupCategory
        GroupScope     = $Group.GroupScope
        Description    = $Group.Description
    }
}

function Get-UserGroupRows {
    param(
        $Users,
        [bool] $Recurse,
        [string] $NameFilter
    )

    foreach ($user in @($Users)) {
        foreach ($group in (Get-UserGroups -User $user -Recurse $Recurse)) {
            if (Test-GroupNameLike -Group $group -Pattern $NameFilter) {
                New-UserGroupRow -User $user -Group $group
            }
        }
    }
}

function Write-UserGroupCsv {
    param(
        $Rows,
        [Parameter(Mandatory)]
        [string] $Path
    )

    $directory = Split-Path -Parent $Path
    if ($directory -and -not (Test-Path -LiteralPath $directory)) {
        throw "CSV folder does not exist: $directory"
    }

    $columns = @(
        'User', 'Name', 'SamAccountName',
        'GroupCategory', 'GroupScope', 'Description'
    )
    @($Rows) | Select-Object $columns | Export-Csv -LiteralPath $Path -NoTypeInformation -Encoding UTF8
    Write-Host "Exported $(@($Rows).Count) row(s) to $Path"
}

function Get-DefaultCsvPath {
    param($Users)

    $selected = @($Users)
    if ($selected.Count -eq 1) {
        $safe = $selected[0].SamAccountName
        foreach ($char in [System.IO.Path]::GetInvalidFileNameChars()) {
            $safe = $safe.Replace([string]$char, '_')
        }
        if ([string]::IsNullOrWhiteSpace($safe)) {
            $safe = 'user'
        }
        return ".\$safe-groups.csv"
    }
    return '.\user-groups.csv'
}

function Invoke-InteractivePrompt {
    Write-Host @'

1) List groups
2) Export groups to CSV
'@
    $choice = Read-HostText -Prompt 'Choose action (1/2)' -Required
    $action = switch -Regex ($choice) {
        '^(1|list)$' { 'List' }
        '^(2|export)$' { 'Export' }
        default { throw "Unknown action '$choice'. Enter 1 or 2." }
    }

    [PSCustomObject]@{
        UserName        = Read-HostText -Prompt 'User name (wildcards * and ? allowed)' -Required
        GroupName       = Read-HostText -Prompt 'Group name filter (optional, wildcards allowed)'
        Recurse         = Read-YesNo -Prompt 'Include nested groups'
        ExportRequested = $action -eq 'Export'
    }
}

Initialize-ActiveDirectoryModule

$exportRequested = [bool]$Export -or -not [string]::IsNullOrWhiteSpace($CsvPath)
$recurse = [bool]$Recursive

if ($PSCmdlet.ParameterSetName -eq 'Interactive') {
    $prompt = Invoke-InteractivePrompt
    $UserName = $prompt.UserName
    $GroupName = $prompt.GroupName
    $exportRequested = [bool]$prompt.ExportRequested
    $recurse = [bool]$prompt.Recurse
}

if ([string]::IsNullOrWhiteSpace($UserName)) {
    $UserName = Read-HostText -Prompt 'User name (wildcards * and ? allowed)' -Required
}

$users = @(Resolve-ADUsers -Name $UserName | Sort-Object SamAccountName)
$selectedUsers = @(Select-ADUser -Users $users -AllMatches:$AllMatchingUsers)

if ($exportRequested -and [string]::IsNullOrWhiteSpace($CsvPath)) {
    $CsvPath = Read-HostText -Prompt 'CSV path' -Default (Get-DefaultCsvPath $selectedUsers) -Required
}

Register-UserGroupDisplay
$rows = @(
    Get-UserGroupRows -Users $selectedUsers -Recurse $recurse -NameFilter $GroupName |
        Sort-Object User, Name
)

if ($rows.Count -eq 0) {
    if ([string]::IsNullOrWhiteSpace($GroupName)) {
        Write-Warning 'No groups found.'
    }
    else {
        Write-Warning "No groups matched '$GroupName'."
    }
}

if (-not [string]::IsNullOrWhiteSpace($CsvPath)) {
    Write-UserGroupCsv -Rows $rows -Path $CsvPath
}

$rows
