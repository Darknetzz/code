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
        $cmd = net use ${letter}: ${uncPath} /persistent:yes /yes;
        Write-Output "Mounting $uncPath to $letter";
        & pwsh.exe -Command "$cmd"
    }
}

net use;