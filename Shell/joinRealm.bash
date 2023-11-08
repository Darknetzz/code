#!/bin/bash
sudo apt install sssd-ad sssd-tools realmd adcli
echo "Type FQDN of domain controller: "
read DC
sudo realm join "$DC"
echo "Enable automatic creation of home directories? [Y/n]"
read HD
if [[ "$HD" -eq "Y" ]] || [[ "$HD" -eq "" ]]
then
    sudo pam-auth-update --enable mkhomedir
fi