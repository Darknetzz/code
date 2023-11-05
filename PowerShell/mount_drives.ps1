# This file is really of no use to the public, but I like to have it readily available to myself.

# Remote execute (you can add this in task scheduler):
# pwsh.exe -Command "iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/Darknetzz/code/main/PowerShell/mount_drives.ps1'));"

$mountPoints = @{
    "X" = "\\NAS1.dark.net\Data"
    "Y" = "\\NAS2.dark.net\Data"
    "Z" = "\\NAS3.dark.net\Share"
    "G" = "\\ha.dark.net\config"
    "H" = "\\ubuntu01.dark.net\data"
    "I" = "\\ubuntu02.dark.net\data"
}

$iterator = $mountPoints.getEnumerator();

foreach ($mp in $iterator) {
    $letter  = $mp.Name;
    $uncPath = $mp.Value;
    If (Get-PSDrive | Where-Object DisplayRoot -EQ $uncPath) { 
        Write-Output "$uncPath already mapped.";
    } else {
        $cmd = "net use ${letter}: ${uncPath} /persistent:yes /yes;"
        Write-Output "Mounting $uncPath to $letter";
        & pwsh.exe -Command "$cmd"
    }
}

net use;