#!/bin/bash

# Ensure the script is run as root
if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root. Use sudo." 1>&2
   exit 1
fi

# Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Update and upgrade apt-get
sudo apt-get update && sudo apt-get upgrade -y

# Install git if it's not installed
if ! git --version &>/dev/null; then
    sudo apt-get install git -y
fi

# Install necessary libraries via pip
pip install requests spidev gpiozero lgpio setuptools Jetson.GPIO

# Clone the Waveshare e-Paper repository
git clone https://github.com/waveshareteam/e-Paper.git
cd e-Paper/RaspberryPi_JetsonNano/python

# Install the e-Paper library
pip install .

# Go back to the home directory
cd ~

# Install cmake and coincurve==19.0.1 with all necessary dependencies
sudo apt-get install -y cmake build-essential pigpio libjpeg-dev zlib1g-dev python3-dev python3-pip git \
libfreetype6-dev liblcms2-dev libopenjp2-7 libtiff5-dev libwebp-dev tcl8.6 tk8.6

# Check cmake version
cmake --version

# Install specific versions of coincurve and additional libraries
pip install coincurve==19.0.1 Pillow qrcode[pil] bip_utils==2.9.3

# Prompt user to manually edit the zpub.json file
echo "Please edit the zpub.json file to set your xpub."
echo "To edit the file, run the following command:"
echo "nano /home/pi/e-Paper/RaspberryPi_JetsonNano/python/examples/zpub.json"

# Prompt user to edit the run_piggybank.sh script
echo "Please check the path in the run_piggybank.sh script and edit it for your environment."
echo "To edit the file, run the following command:"
echo "nano /home/pi/run_piggybank.sh"

# Set execute permissions on run_piggybank.sh
chmod +x /home/pi/run_piggybank.sh

# Add the run_piggybank.sh to crontab for boot execution
echo "@reboot /home/pi/run_piggybank.sh >> /home/pi/piggybank.log 2>&1" | crontab -

# Confirmation message
echo "Setup completed. Ensure you have edited zpub.json and run_piggybank.sh files before rebooting."
