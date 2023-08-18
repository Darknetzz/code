#Requires -RunAsAdministrator

# Config
$hostname = [System.Net.Dns]::GetHostName()
$user = "Gjest"


# Check if user is signed in
$sessionID = ((quser /server:"$hostname" | Where-Object { $_ -match "$user" }) -split ' +')[2]

if ($sessionID) {
    Write-Output "User $user signed in. Killing session..."
    logoff $sessionID
} else {
    Write-Output "User $user not signed in."
}

# Delete the account in question
net user $user /delete

# Delete the user folder
Remove-Item "C:\Users\$user" -Recurse -Force

# Add it again
net user $user /add /active:yes
net localgroup users $user /delete
net localgroup Administrators $user /add

# test