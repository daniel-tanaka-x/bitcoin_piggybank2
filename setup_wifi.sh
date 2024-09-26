#!/bin/bash
SSID=$1
PASSWORD=$2
WPA_SUPPLICANT_CONF="/etc/wpa_supplicant/wpa_supplicant.conf"

echo "
network={
    ssid=\"$SSID\"
    psk=\"$PASSWORD\"
}" >> $WPA_SUPPLICANT_CONF

sudo wpa_cli -i wlan0 reconfigure
