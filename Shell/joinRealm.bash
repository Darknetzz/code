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

# We should edit /etc/sudoers.d here, not the main sudoers file.
# https://askubuntu.com/questions/455211/how-to-add-domain-admins-to-sudoers
echo "Add domain admins to sudoers file?"
read ADS
if [[ "$ADS" -eq "Y" ]] || [[ "$ADS" -eq "" ]]
then
    LINE="# Add domain admins to sudoers
    \"%MYDOMAIN\Domain Admins\" ALL=(ALL) ALL"
    echo "$LINE" > /etc/sudoers.d/DomainAdmins
fi