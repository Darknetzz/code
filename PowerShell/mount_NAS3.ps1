# This file is really of no use to the public, but I like to have it readily available to myself.

# Remote execute:
# pwsh -Command "iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/Darknetzz/code/main/PowerShell/mount_NAS3.ps1'))"

$mountPoints = @{
    "Z" = "\\ubuntu02.dark.net\share"
    "Y" = "\\10.0.2.56\data"
}

$iterator = $mountPoints.getEnumerator();

foreach ($mp in $iterator) {
    $letter  = $mp.Name;
    $uncPath = $mp.Value;
    If (Get-PSDrive | Where-Object DisplayRoot -EQ $uncPath) { 
        Write-Output "$uncPath already mapped.";
    } else {
        Write-Output "Mounting $uncPath to $letter";
        $cmd = "net use", "$letter", ":", "$uncPath", "/persistent:yes", "/yes";
        pwsh.exe $cmd
    }
}

net use;