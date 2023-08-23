$mountPoints = @{
    "Z" = "\\fileshare.local\share"
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
        net use $letter: "$uncPath" /persistent:yes /yes;
    }
}

net use;