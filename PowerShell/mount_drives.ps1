# This file is really of no use to the public, but I like to have it readily available to myself.

# Remote execute (you can add this in task scheduler):
# pwsh.exe -Command "iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/Darknetzz/code/main/PowerShell/mount_drives.ps1'));"



<#
.SYNOPSIS
    Retrieves the credentials for mounting drives.

.DESCRIPTION
    The getCredentials function retrieves the credentials required for mounting drives. It first attempts to retrieve the credentials with the specified credential name ("DARK.NET"). If the credentials are not found, it falls back to retrieving the credentials for the current user.

.OUTPUTS
    System.Management.Automation.PSCredential
        The retrieved credentials.

.EXAMPLE
    $credentials = getCredentials
    # Retrieves the credentials for mounting drives.

#>
function getCredentials($credentialName = "DARK.NET") {
    $credential = Get-Credential -ErrorAction SilentlyContinue -UserName $credentialName
    if ($credential -eq $null) {
        $credential = Get-Credential -ErrorAction SilentlyContinue -UserName $env:USERNAME
    }
    return $credential
}

$credential = getCredentials

$mountPoints = @{
    "X" = "\\NAS1.dark.net\Data"
    "Y" = "\\NAS2.dark.net\Data"
    "Z" = "\\NAS3.dark.net\Share"
    # "G" = "\\ha.dark.net\config"
    # "H" = "\\ubuntu01.dark.net\data"
    # "I" = "\\ubuntu02.dark.net\data"
}

$iterator = $mountPoints.getEnumerator();

foreach ($mp in $iterator) {
    $letter  = $mp.Name;
    $uncPath = $mp.Value;
    If (Get-PSDrive | Where-Object DisplayRoot -EQ $uncPath) { 
        Write-Output "$uncPath already mapped.";
    } else {
        
        $cmd = "net use ${letter}: ${uncPath} /persistent:yes /yes /user:$env:USERNAME"
        $cmd = "net use ${letter}: ${uncPath} /persistent:yes /yes /user:$($credential.UserName)"

        Write-Output "Mounting $uncPath to $letter";
        $timeoutSeconds = 10
        $process = Start-Process -FilePath "pwsh.exe" -ArgumentList "-Command", "$cmd" -PassThru
        $process.WaitForExit($timeoutSeconds * 1000)
        if (-not $process.HasExited) {
            $process.Kill()
            Write-Output "Process timed out."
        }
        
    }
}

net use;