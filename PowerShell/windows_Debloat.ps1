#Requires -RunAsAdministrator

# ──────────────────────────────────────────────────────────────────────────── #
#                                   Functions                                  #
# ──────────────────────────────────────────────────────────────────────────── #
function Set-RegValue($path, $valueName, $valueData) {
    try{  
        $getValue = Get-ItemPropertyValue -Path $path -Name $valueName -ErrorAction Stop
        if ($getValue -eq $valueData) {
            Write-Output "[SKIPPING] Registry key $valueName already $valueData"
            Return
        }
    }  
    catch [System.Management.Automation.ItemNotFoundException] {  
        New-Item -Path $path -Force  
        New-ItemProperty -Path $path -Name $ValueName -Value $ValueData -Force
        Write-Output "[CREATED] Registry key $valueName created with value $valueData"
    }  
    catch {
        New-ItemProperty -Path $path -Name $ValueName -Value $ValueData -Type String -Force
        Write-Output "[CREATED] Registry key $valueName created with value $valueData"
    }
}

function Remove-File($path, $file) {
    try {
        Get-ItemProperty -Path "$path\$file" -Name $valueName -ErrorAction Stop
        Remove-Item -Path "$path\$file"
        Write-Output "[DELETED] $file"
    }
    catch {
        Write-Output "[SKIPPING] $file doesn't exist"
        Return
    }
}

# ──────────────────────────────────────────────────────────────────────────── #
#                                    Config                                    #
# ──────────────────────────────────────────────────────────────────────────── #
$user = $Env:UserName
$userFolder = "C:\Users\$user"

# ──────────────────────────────────────────────────────────────────────────── #
#                             Registry keys to edit                            #
# ──────────────────────────────────────────────────────────────────────────── #
# Create a hashtable with registry paths as keys and lists of key-value pairs as values
# Create a hashtable with registry paths as keys and lists of key-value pairs as values
$registryKeys = @{
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" = @{
        "ShowTaskViewButton" = "0"
        "TaskbarDa" = "0"
        "TaskbarMn" = "0"
        "TaskbarAl" = "0"
        "HideFileExt" = "0"
    }
    "HKLM:\Software\Policies\Microsoft\Windows\OOBE" = @{
        "DisablePrivacyExperience" = "1"
    }
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Search" = @{
        "SearchboxTaskbarMode" = "0"
    }
}


# ──────────────────────────────────────────────────────────────────────────── #
#                                Files to delete                               #
# ──────────────────────────────────────────────────────────────────────────── #
$filesToDelete = @{
    "$userFolder\AppData\Roaming\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar" = @(
        "Microsoft Edge.lnk"
    )
}

# ──────────────────────────────────────────────────────────────────────────── #
#                                   Iterators                                  #
# ──────────────────────────────────────────────────────────────────────────── #
# Iterate through the keys and values
foreach ($key in $registryKeys.Keys) {
    Write-Host "=== [$key] ==="
    $keyValuePairs = $registryKeys[$key]
    foreach ($subKey in $keyValuePairs.Keys) {
        $value = $keyValuePairs[$subKey]
        Set-RegValue "$key" "$subKey" "$value"
    }
    Write-Output ""
}

foreach ($filePath in $filesToDelete.Keys) {
    Write-Output "=== [$filePath] ==="

    $files = $filesToDelete[$filePath]
    foreach ($file in $files) {
        Remove-File "$filePath" "$file"
    }
    Write-Output ""
}

# REG LOAD HKLM\Default C:\Users\$user\NTUSER.DAT
 
taskkill /f /im explorer.exe

Start-Process explorer.exe

# update
#test