<#
.SYNOPSIS
    Lists, exports, or tests Active Directory group membership.

.DESCRIPTION
    Domain Active Directory only (RSAT ActiveDirectory module).

    With no parameters, prompts for the action and the values it needs.
    Wildcards * and ? are allowed in -GroupName and -UserName.

    The default action is to list members. -UserName then filters that list
    (SamAccountName, display name, or UPN). -CsvPath or -Export writes the
    same rows to CSV. -Test checks whether each matching user belongs to each
    matching group.

    When several groups match and -AllMatchingGroups is not set, matching
    groups are shown and you are prompted to pick.

    Get-ADGroupMember does not return a user's primary group. Membership tests
    treat the primary group as direct membership.

.PARAMETER GroupName
    Group name or sAMAccountName. Wildcards * and ? are allowed.
    If omitted, you are prompted.

.PARAMETER UserName
    With -Test, the user to check (sAMAccountName, UPN, or display name).
    Without -Test, an optional filter on listed members.
    Wildcards * and ? are allowed. If omitted with -Test, you are prompted.

.PARAMETER Test
    Test membership instead of listing members.

.PARAMETER Recursive
    Include members of nested groups. With -Test, nested membership counts.

.PARAMETER Export
    Write the member listing to CSV. Prompts for a path when -CsvPath is omitted.

.PARAMETER CsvPath
    CSV file to write. Parent folder must already exist. Implies export.

.PARAMETER AllMatchingGroups
    Process every group that matches -GroupName instead of prompting.

.EXAMPLE
    .\AD-Group.ps1
    Prompts for the action and any missing values.

.EXAMPLE
    .\AD-Group.ps1 -GroupName 'App-Admins'

.EXAMPLE
    .\AD-Group.ps1 -GroupName 'App-Admins' -Recursive

.EXAMPLE
    .\AD-Group.ps1 -GroupName 'App-Admins' -UserName 'kr*'

.EXAMPLE
    .\AD-Group.ps1 -GroupName 'App-Admins' -CsvPath '.\members.csv'

.EXAMPLE
    .\AD-Group.ps1 -GroupName 'App-Admins' -Export
    Prompts for the CSV path.

.EXAMPLE
    .\AD-Group.ps1 -Test -GroupName 'App-Admins' -UserName 'kriss'

.EXAMPLE
    .\AD-Group.ps1 -Test -GroupName '*admins*' -UserName 'kr*'

.EXAMPLE
    .\AD-Group.ps1 -GroupName '*admins*' -AllMatchingGroups

.NOTES
    Requires the ActiveDirectory module (RSAT).
#>

[CmdletBinding(DefaultParameterSetName = 'Interactive')]
param(
    [Parameter(ParameterSetName = 'List', Position = 0)]
    [Parameter(ParameterSetName = 'Test', Position = 0)]
    [string] $GroupName,

    [Parameter(ParameterSetName = 'List', Position = 1)]
    [Parameter(ParameterSetName = 'Test', Position = 1)]
    [string] $UserName,

    [Parameter(ParameterSetName = 'Test', Mandatory)]
    [switch] $Test,

    [Parameter(ParameterSetName = 'List')]
    [Parameter(ParameterSetName = 'Test')]
    [switch] $Recursive,

    [Parameter(ParameterSetName = 'List')]
    [switch] $Export,

    [Parameter(ParameterSetName = 'List')]
    [string] $CsvPath,

    [Parameter(ParameterSetName = 'List')]
    [Parameter(ParameterSetName = 'Test')]
    [switch] $AllMatchingGroups
)

$ErrorActionPreference = 'Stop'

$script:MemberRowTypeName = 'Code.ADGroupMember'

function ConvertTo-ADFilterLiteral {
    param([string] $Value)
    return $Value.Replace("'", "''")
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
    Import-Module ActiveDirectory -ErrorAction Stop
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

function Register-MemberRowDisplay {
    if (Get-TypeData -TypeName $script:MemberRowTypeName) {
        return
    }
    Update-TypeData -TypeName $script:MemberRowTypeName -DefaultDisplayPropertySet @(
        'Group', 'SamAccountName', 'DisplayName', 'Enabled'
    ) -Force
}

function Get-ADGroupByLike {
    param(
        [string] $Name,
        [string[]] $Properties
    )

    $pattern = ConvertTo-ADFilterLiteral $Name
    $filter = "Name -like '$pattern' -or SamAccountName -like '$pattern'"
    return @(Get-ADGroup -Filter $filter -Properties $Properties | Where-Object { $_ })
}

function Resolve-ADGroups {
    param([Parameter(Mandatory)][string] $Name)

    $properties = @('Description', 'member')
    if (Test-WildcardPattern $Name) {
        return @(Get-ADGroupByLike -Name $Name -Properties $properties)
    }

    try {
        return @(Get-ADGroup -Identity $Name -Properties $properties -ErrorAction Stop | Where-Object { $_ })
    }
    catch {
        if (-not (Test-ADIdentityNotFound $_)) { throw }
    }

    return @(Get-ADGroupByLike -Name $Name -Properties $properties)
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

function Get-DirectMemberCount {
    param($Group)

    $raw = $null
    if ($Group.PSObject.Properties.Name -contains 'member') {
        $raw = $Group.member
    }
    if ($null -eq $raw -and ($Group.PSObject.Properties.Name -contains 'Members')) {
        $raw = $Group.Members
    }
    if ($null -eq $raw) {
        return 0
    }
    return @($raw).Count
}

function Get-PrincipalClass {
    param($Member)

    $classes = @($Member.objectClass)
    foreach ($candidate in @('user', 'computer', 'group')) {
        if ($classes -contains $candidate) {
            return $candidate
        }
    }
    if ($classes.Count -eq 0) {
        return ''
    }
    return [string]$classes[-1]
}

function Select-ADGroup {
    param(
        [Parameter(Mandatory)]
        $Groups,

        [switch] $AllMatches
    )

    $matched = @($Groups | Where-Object { $_ })
    if ($matched.Count -eq 0) {
        throw "No groups matched '$GroupName'."
    }
    if ($matched.Count -eq 1 -or $AllMatches) {
        return $matched
    }

    if (-not [Environment]::UserInteractive) {
        throw "Multiple groups matched '$GroupName'. Pass -AllMatchingGroups or a more specific -GroupName."
    }

    $index = 1
    $summary = foreach ($group in $matched) {
        [PSCustomObject]@{
            Index             = $index
            Name              = $group.Name
            SamAccountName    = $group.SamAccountName
            Description       = $group.Description
            DistinguishedName = $group.DistinguishedName
            MemberCount       = Get-DirectMemberCount $group
        }
        $index++
    }
    $summary | Format-Table -AutoSize | Out-Host

    $answer = Read-HostText -Prompt "Multiple groups matched. Enter a number, comma-separated numbers, or 'all'" -Required
    if ($answer -eq 'all') {
        return $matched
    }

    $seen = @{}
    $picked = foreach ($part in ($answer -split '[,\s]+' | Where-Object { $_ })) {
        $number = 0
        if (-not [int]::TryParse($part, [ref]$number) -or $number -lt 1 -or $number -gt $matched.Count) {
            throw "Invalid selection '$part'."
        }
        $group = $matched[$number - 1]
        if ($seen.ContainsKey($group.DistinguishedName)) {
            continue
        }
        $seen[$group.DistinguishedName] = $true
        $group
    }

    $picked = @($picked | Where-Object { $_ })
    if ($picked.Count -eq 0) {
        throw "No groups selected."
    }
    return $picked
}

function Get-RawGroupMembers {
    param(
        $Group,
        [bool] $Recurse
    )

    return @(Get-ADGroupMember -Identity $Group.DistinguishedName -Recursive:$Recurse | Where-Object { $_ })
}

function Get-ADAccountMap {
    param(
        [string[]] $DistinguishedNames,
        [ValidateSet('User', 'Computer')]
        [string] $Type
    )

    $map = @{}
    $names = @($DistinguishedNames | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($names.Count -eq 0) {
        return $map
    }

    $command = if ($Type -eq 'User') { 'Get-ADUser' } else { 'Get-ADComputer' }
    $properties = if ($Type -eq 'User') {
        @('DisplayName', 'UserPrincipalName', 'Enabled')
    }
    else {
        @('Enabled')
    }

    $chunkSize = 25
    for ($offset = 0; $offset -lt $names.Count; $offset += $chunkSize) {
        $end = [Math]::Min($offset + $chunkSize - 1, $names.Count - 1)
        $chunk = @($names[$offset..$end])
        $filter = @(foreach ($dn in $chunk) {
                "DistinguishedName -eq '$(ConvertTo-ADFilterLiteral $dn)'"
            }) -join ' -or '

        foreach ($account in (& $command -Filter $filter -Properties $properties)) {
            $map[$account.DistinguishedName] = $account
        }
    }

    return $map
}

function New-MemberRow {
    param(
        $Group,
        [string] $SamAccountName,
        [string] $DisplayName,
        [string] $UserPrincipalName,
        $Enabled,
        [string] $ObjectClass
    )

    return [PSCustomObject]@{
        PSTypeName        = $script:MemberRowTypeName
        Group             = $Group.SamAccountName
        SamAccountName    = $SamAccountName
        DisplayName       = $DisplayName
        UserPrincipalName = $UserPrincipalName
        Enabled           = $Enabled
        ObjectClass       = $ObjectClass
    }
}

function Test-MemberNameLike {
    param(
        $Record,
        [string] $Pattern
    )

    if ([string]::IsNullOrWhiteSpace($Pattern)) {
        return $true
    }
    foreach ($value in @($Record.SamAccountName, $Record.DisplayName, $Record.UserPrincipalName)) {
        if ($value -like $Pattern) {
            return $true
        }
    }
    return $false
}

function Get-GroupMemberObjects {
    param(
        $Groups,
        [bool] $Recurse,
        [string] $NameFilter
    )

    foreach ($group in @($Groups)) {
        $raw = @(Get-RawGroupMembers -Group $group -Recurse $Recurse)
        $userDns = @(
            $raw |
                Where-Object { (Get-PrincipalClass $_) -eq 'user' } |
                Select-Object -ExpandProperty DistinguishedName
        )
        $computerDns = @(
            $raw |
                Where-Object { (Get-PrincipalClass $_) -eq 'computer' } |
                Select-Object -ExpandProperty DistinguishedName
        )
        $users = Get-ADAccountMap -DistinguishedNames $userDns -Type User
        $computers = Get-ADAccountMap -DistinguishedNames $computerDns -Type Computer

        foreach ($member in $raw) {
            $class = Get-PrincipalClass $member
            $row = switch ($class) {
                'user' {
                    $account = $users[$member.DistinguishedName]
                    if ($account) {
                        $displayName = if ($account.DisplayName) { $account.DisplayName } else { $account.Name }
                        New-MemberRow $group $account.SamAccountName $displayName $account.UserPrincipalName $account.Enabled 'user'
                    }
                    else {
                        New-MemberRow $group $member.SamAccountName $member.Name $null $null 'user'
                    }
                }
                'computer' {
                    $account = $computers[$member.DistinguishedName]
                    $enabled = if ($account) { $account.Enabled } else { $null }
                    $sam = if ($account) { $account.SamAccountName } else { $member.SamAccountName }
                    $displayName = if ($account) { $account.Name } else { $member.Name }
                    New-MemberRow $group $sam $displayName $null $enabled 'computer'
                }
                default {
                    New-MemberRow $group $member.SamAccountName $member.Name $null $null $class
                }
            }

            if (Test-MemberNameLike -Record $row -Pattern $NameFilter) {
                $row
            }
        }
    }
}

function Test-ADGroupMembership {
    param(
        $Users,
        $Groups,
        [bool] $Recurse
    )

    foreach ($group in @($Groups)) {
        $memberDns = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
        foreach ($member in (Get-RawGroupMembers -Group $group -Recurse $Recurse)) {
            if ($member.DistinguishedName) {
                [void]$memberDns.Add([string]$member.DistinguishedName)
            }
        }

        foreach ($user in @($Users)) {
            $isMember = $memberDns.Contains([string]$user.DistinguishedName)
            if (-not $isMember -and $user.PrimaryGroup -and ($user.PrimaryGroup -eq $group.DistinguishedName)) {
                $isMember = $true
            }

            [PSCustomObject]@{
                User      = $user.SamAccountName
                Group     = $group.SamAccountName
                IsMember  = $isMember
                Recursive = $Recurse
            }
        }
    }
}

function Write-GroupMemberCsv {
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
        'Group', 'SamAccountName', 'DisplayName',
        'UserPrincipalName', 'Enabled', 'ObjectClass'
    )
    @($Rows) | Select-Object $columns | Export-Csv -LiteralPath $Path -NoTypeInformation -Encoding UTF8
    Write-Host "Exported $(@($Rows).Count) row(s) to $Path"
}

function Get-DefaultCsvPath {
    param($Groups)

    $selected = @($Groups)
    if ($selected.Count -eq 1) {
        $safe = $selected[0].SamAccountName
        foreach ($char in [System.IO.Path]::GetInvalidFileNameChars()) {
            $safe = $safe.Replace([string]$char, '_')
        }
        if ([string]::IsNullOrWhiteSpace($safe)) {
            $safe = 'group'
        }
        return ".\$safe-members.csv"
    }
    return '.\group-members.csv'
}

function Invoke-InteractivePrompt {
    Write-Host @'

1) List members
2) Test membership
3) Export members to CSV
'@
    $choice = Read-HostText -Prompt 'Choose action (1/2/3)' -Required
    $action = switch -Regex ($choice) {
        '^(1|list)$' { 'List' }
        '^(2|test)$' { 'Test' }
        '^(3|export)$' { 'Export' }
        default { throw "Unknown action '$choice'. Enter 1, 2, or 3." }
    }

    [PSCustomObject]@{
        GroupName       = Read-HostText -Prompt 'Group name (wildcards * and ? allowed)' -Required
        UserName        = if ($action -eq 'Test') {
            Read-HostText -Prompt 'User name (wildcards * and ? allowed)' -Required
        }
        else {
            Read-HostText -Prompt 'User name filter (optional, wildcards allowed)'
        }
        Recurse         = Read-YesNo -Prompt 'Include nested groups'
        ExportRequested = $action -eq 'Export'
        RunTest         = $action -eq 'Test'
    }
}

Initialize-ActiveDirectoryModule

$runTest = [bool]$Test
$exportRequested = [bool]$Export -or -not [string]::IsNullOrWhiteSpace($CsvPath)
$recurse = [bool]$Recursive

if ($PSCmdlet.ParameterSetName -eq 'Interactive') {
    $prompt = Invoke-InteractivePrompt
    $GroupName = $prompt.GroupName
    $UserName = $prompt.UserName
    $runTest = [bool]$prompt.RunTest
    $exportRequested = [bool]$prompt.ExportRequested
    $recurse = [bool]$prompt.Recurse
}

if ([string]::IsNullOrWhiteSpace($GroupName)) {
    $GroupName = Read-HostText -Prompt 'Group name (wildcards * and ? allowed)' -Required
}

$groups = @(Resolve-ADGroups -Name $GroupName | Sort-Object Name, SamAccountName)
$selectedGroups = @(Select-ADGroup -Groups $groups -AllMatches:$AllMatchingGroups)

if ($runTest) {
    if ([string]::IsNullOrWhiteSpace($UserName)) {
        $UserName = Read-HostText -Prompt 'User name (wildcards * and ? allowed)' -Required
    }

    $users = @(Resolve-ADUsers -Name $UserName | Sort-Object SamAccountName)
    if ($users.Count -eq 0) {
        throw "No users matched '$UserName'."
    }

    Test-ADGroupMembership -Users $users -Groups $selectedGroups -Recurse $recurse |
        Sort-Object Group, User
    return
}

if ($exportRequested -and [string]::IsNullOrWhiteSpace($CsvPath)) {
    $CsvPath = Read-HostText -Prompt 'CSV path' -Default (Get-DefaultCsvPath $selectedGroups) -Required
}

Register-MemberRowDisplay
$rows = @(
    Get-GroupMemberObjects -Groups $selectedGroups -Recurse $recurse -NameFilter $UserName |
        Sort-Object Group, SamAccountName, ObjectClass
)

if ($rows.Count -eq 0) {
    if ([string]::IsNullOrWhiteSpace($UserName)) {
        Write-Warning 'No members found.'
    }
    else {
        Write-Warning "No members matched '$UserName'."
    }
}

if (-not [string]::IsNullOrWhiteSpace($CsvPath)) {
    Write-GroupMemberCsv -Rows $rows -Path $CsvPath
}

$rows
