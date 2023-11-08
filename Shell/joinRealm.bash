#!/bin/bash
sudo apt install sssd-ad sssd-tools realmd adcli
echo "Type FQDN of domain controller: "
read DC
echo "Username to join with (default: Administrator): "
read USER
if [[ "$USER" -neq "" ]]
then
    USER="-U $USER"
else
    USER=""
fi
sudo realm join "$USER" "$DC"
echo "Enable automatic creation of home directories? [Y/n]"
read HD
if [[ "$HD" -eq "Y" ]] || [[ "$HD" -eq "" ]]
then
    sudo pam-auth-update --enable mkhomedir
fi