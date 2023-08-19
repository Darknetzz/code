#Requires -RunAsAdministrator

# ──────────────────────────────────────────────────────────────────────────── #
#                                   Functions                                  #
# ──────────────────────────────────────────────────────────────────────────── #
function Set-RegValue($path, $valueName, $valueData) {
    try{  
        Get-ItemProperty -Path $path -Name $valueName -ErrorAction Stop
    }  
    catch [System.Management.Automation.ItemNotFoundException] {  
        New-Item -Path $path -Force  
        New-ItemProperty -Path $path -Name $ValueName -Value $ValueData -Force -PropertyType Dword
    }  
    catch {  
        New-ItemProperty -Path $path -Name $ValueName -Value $ValueData -Type String -Force -PropertyType Dword
    }  
}

# ──────────────────────────────────────────────────────────────────────────── #
#                                    Config                                    #
# ──────────────────────────────────────────────────────────────────────────── #
$user = $Env:UserName
$userFolder = "C:\Users\$user"
$taskBarFolder = "$userFolder\AppData\Roaming\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"
$regPath = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"

$values = "ShowTaskViewButton", "TaskbarDa", "TaskbarMn", "TaskbarAl", "HideFileExt"

# ──────────────────────────────────────────────────────────────────────────── #
#                             Registry keys to edit                            #
# ──────────────────────────────────────────────────────────────────────────── #
$registryKeys = @{
    ShowTaskViewButton = 0
    TaskbarDa          = 0
    TaskbarMn          = 0
    TaskbarAl          = 0
    HideFileExt        = 0
}

# ──────────────────────────────────────────────────────────────────────────── #
#                                Files to delete                               #
# ──────────────────────────────────────────────────────────────────────────── #
$filesToDelete = 
"$taskBarFolder\Microsoft Edge.lnk",
"$taskBarFolder\Microsoft Edge.lnk"

foreach ($valueName in $values) {
    Set-RegValue($regPath, $valueName, "0")
}

Remove-Item /f "$userFolder\AppData\Roaming\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\Microsoft Edge.lnk"

# REG LOAD HKLM\Default C:\Users\$user\NTUSER.DAT

# Removes search from the Taskbar
reg.exe add "HKLM\Default\SOFTWARE\Microsoft\Windows\CurrentVersion\Search" /v SearchboxTaskbarMode /t REG_DWORD /d 0 /f
 
taskkill /f /im explorer.exe

Start-Process explorer.exe
pause