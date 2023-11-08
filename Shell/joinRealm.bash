#!/bin/bash
sudo apt install sssd-ad sssd-tools realmd adcli
echo "Type FQDN of domain controller: "
read DC
echo "Username to join with (default: Administrator): "
read USER
if [[ "$USER" -ne "" ]]
then
    JOIN="$(sudo realm join -v -U $USER $DC)"
else
    JOIN="$(sudo realm join -v $DC)"
fi
$($JOIN)
echo "Enable automatic creation of home directories? [Y/n]"
read HD
if [[ "$HD" -eq "Y" ]] || [[ "$HD" -eq "" ]]
then
    sudo pam-auth-update --enable mkhomedir
fi