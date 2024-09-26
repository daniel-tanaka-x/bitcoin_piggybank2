#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import random
from PIL import Image, ImageDraw, ImageFont
from bip_utils import (
    Bip39MnemonicGenerator,
    Bip39SeedGenerator,
    Bip39Languages,
    Bip32Slip10Secp256k1,  # Use BIP32 for hierarchical key derivation
    Bip84Coins
)

# --- E-Ink Display Setup ---

# Adjust the path to the e-Paper library
sys.path.append('/home/pi/e-Paper/RaspberryPi_JetsonNano/python/lib')  # Adjust as needed
from waveshare_epd import epd2in13_V4  # Adjusted for 2.13-inch V4 HAT

# Initialize e-ink display
epd = epd2in13_V4.EPD()
epd.init()
epd.Clear(0xFF)

# Define smaller fonts (small size for the 2.13-inch display)
font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
font_title = ImageFont.truetype(font_path, 12)  # Smaller font for the title
font_text = ImageFont.truetype(font_path, 10)   # Smaller font for the mnemonic and passphrase

# --- Seed Generation and Derivation Functions ---

def generate_random_passphrase(length=12):
    chars = (
        'abcdefghijkmnpqrstuvwxyz'
        'ABCDEFGHJKLMNPQRSTUVWXYZ'
        '0123456789'
        '!@#$%^&*()=+[]{}'
    )
    return ''.join(random.SystemRandom().choice(chars) for _ in range(length))

def generate_random_index():
    return random.SystemRandom().randint(0, 2**31 - 1)  # BIP32 index range

def generate_12_word_seed():
    # Generate 128-bit entropy for a 12-word mnemonic
    entropy_bytes = os.urandom(16)  # 128-bit entropy = 16 bytes for 12-word mnemonic
    mnemonic = Bip39MnemonicGenerator(Bip39Languages.ENGLISH).FromEntropy(entropy_bytes)
    return mnemonic.ToStr()

def generate_seed_and_passphrase():
    mnemonic = generate_12_word_seed()  # 12-word mnemonic
    passphrase = generate_random_passphrase()
    return mnemonic, passphrase  # Return mnemonic and passphrase

def derive_xpub(seed_phrase, passphrase):
    # Derive the xpub from the seed and passphrase using BIP84 (SegWit)
    seed_bytes = Bip39SeedGenerator(seed_phrase).Generate(passphrase)
    bip32_ctx = Bip32Slip10Secp256k1.FromSeed(seed_bytes)
    xpub = bip32_ctx.PublicKey().ToExtended()  # Get xpub
    return xpub

def derive_child_seed(parent_seed_phrase, parent_passphrase, index):
    # Derive child seed using BIP32 path with the given index (using same 12-word mnemonic)
    seed_bytes = Bip39SeedGenerator(parent_seed_phrase).Generate(parent_passphrase)
    bip32_ctx = Bip32Slip10Secp256k1.FromSeed(seed_bytes)
    child_ctx = bip32_ctx.DerivePath([0, index])  # Derive child at path m/0/{index}
    child_seed_bytes = child_ctx.PrivateKey().Raw().ToBytes()
    child_mnemonic = generate_12_word_seed()  # Force 12-word mnemonic
    return child_mnemonic

# Function to display data
def display_data(title, mnemonic, passphrase, xpub=None, index=None):
    # Create a blank image
    image = Image.new('1', (epd.height, epd.width), 255)  # 1-bit color (white background)
    draw = ImageDraw.Draw(image)

    # Draw the title (left-aligned)
    draw.text((5, 5), title, font=font_title, fill=0)

    # Display mnemonic (split into 3 lines)
    mnemonic_lines = mnemonic.split()  # Split the mnemonic into words
    y_text = 25
    draw.text((5, y_text), ' '.join(mnemonic_lines[:4]), font=font_text, fill=0)  # First line of mnemonic
    draw.text((5, y_text + 15), ' '.join(mnemonic_lines[4:8]), font=font_text, fill=0)  # Second line
    draw.text((5, y_text + 30), ' '.join(mnemonic_lines[8:]), font=font_text, fill=0)  # Third line

    # Display passphrase (left-aligned)
    draw.text((5, y_text + 55), f"Passphrase: {passphrase}", font=font_text, fill=0)

    # Display the index only for child and grandchild seeds
    if title != 'Parent Seed' and index is not None:
        draw.text((5, y_text + 80), f"Index: {index}", font=font_text, fill=0)

    # Display the image
    epd.display(epd.getbuffer(image.rotate(0, expand=True)))

def cycle_display(data_list, cycle_time=30):
    try:
        while True:
            for data in data_list:
                display_data(*data)
                time.sleep(cycle_time)
    except KeyboardInterrupt:
        print('Exiting cycle_display...')
        return

def main():
    # Generate parent seed and passphrase
    parent_mnemonic, parent_passphrase = generate_seed_and_passphrase()
    parent_xpub = derive_xpub(parent_mnemonic, parent_passphrase)  # Derive xpub for parent

    # List to store all generations
    data_list = [('Parent Seed', parent_mnemonic, parent_passphrase, parent_xpub)]  # No index for parent seed

    # Generate 9 more generations (10 in total including parent)
    prev_mnemonic = parent_mnemonic
    prev_passphrase = parent_passphrase
    for i in range(1, 10):
        index = generate_random_index()
        mnemonic = derive_child_seed(prev_mnemonic, prev_passphrase, index)
        passphrase = generate_random_passphrase()
        xpub = derive_xpub(mnemonic, passphrase)
        
        data_list.append((f'Generation {i}', mnemonic, passphrase, xpub, index))
        
        # Update previous mnemonic and passphrase for next generation
        prev_mnemonic = mnemonic
        prev_passphrase = passphrase

    # Start cycling display
    cycle_display(data_list, cycle_time=30)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Exiting...')
        epd.sleep()
        epd.Dev_exit()
        sys.exit()
