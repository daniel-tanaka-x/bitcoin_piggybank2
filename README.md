# Bitcoin Piggybank

Save your sats in a Bitcoin Piggybank!

The Bitcoin Piggybank is an E-Ink-based Bitcoin address generator that works from an xpub file. It generates a new unused Bitcoin address each time it detects an incoming transaction, continuing until the total number of UTXOs reaches 21. Once the limit is hit, it will stop displaying Bitcoin addresses and switch to a message prompting you to move your sats elsewhere. It only supports SegWit, just so you know.

![ダウンロード (41)](https://github.com/user-attachments/assets/1390a4c8-eb66-488e-9806-f5a0d80675eb)

This is just an example. Feel free to customize the messages displayed.

## Hardware list
- Raspberry Pi Zero 2W: https://www.raspberrypi.com/products/raspberry-pi-zero-2-w/
- Waveshare 2.13inch E-Ink display HAT for Raspberry Pi: https://www.waveshare.com/2.13inch-e-paper-hat.htm
- microSD card 4GB or more [use Raspberry Pi OS Lite (32-bit)]
- Raspberry Pi Charger and/or mobile battery for Raspberry Pi (I use mobile battery named [UPS-Lite V1.2 Power Board + Battery])
- Mobile, PC or HWW to make a seed and generate a HD BIP89 SegWit zpub string.

Unfortunately, I don't have the skills to create 3D models for this project, so there are no available cases for it. 

## Commands to prepare the environment
You can run the `setup_piggybank.sh` script to install libraries for piggybank. However, it doesn't cover other functions yet.

# Automatic shutdown
If you need it to be connected to electricity 24/7, it's better to set up an automatic shutdown using systemd and use a SwitchBot Plug or smart plug to power it on.

First, set up shutdown_after_30min.service
```
sudo nano /etc/systemd/system/shutdown_after_30min.service
```
```
[Unit]
Description=Shut down the Raspberry Pi after 30 minutes

[Service]
Type=oneshot
ExecStart=/sbin/shutdown -h now

[Install]
WantedBy=multi-user.target
```

Set up shutdown_after_30min.timer
```
sudo nano /etc/systemd/system/shutdown_after_30min.timer
```
```
[Unit]
Description=Run shutdown service 30 minutes after boot

[Timer]
OnBootSec=30min
Unit=shutdown_after_30min.service

[Install]
WantedBy=timers.target
```
Enable and start it.
```
sudo systemctl enable shutdown_after_30min.timer
sudo systemctl start shutdown_after_30min.timer

