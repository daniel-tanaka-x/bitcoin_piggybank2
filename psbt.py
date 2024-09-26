#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import base64
import logging
import platform
from waveshare_epd import epd2in13_V4  # Import the Waveshare E-Ink display driver
import time
from PIL import Image, ImageDraw, ImageFont
import qrcode
import requests
import json
import base64
from bip_utils import Bip84, Bip84Coins, Bip44Changes
from bitcointx.wallet import CCoinAddress
from bitcointx.core import COutPoint, lx, CTxIn, CTxOut, CMutableTransaction
from bitcointx.core.psbt import PartiallySignedTransaction, PSBT_Input, PSBT_Output
from bitcointx.core.script import CScript

# Set up paths for fonts and images
picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

# Initialize logging
logging.basicConfig(level=logging.DEBUG)
time.sleep(30) # This sleep is to avoid fetching the data before the setup gets ready

# ==========================
# Load zpub from file
# ==========================
def load_zpub():
    zpub_file = "zpub.json" # File to store the zpub
    if os.path.exists(zpub_file):
        with open(zpub_file, 'r') as f:
            data = json.load(f)
            return data.get("zpub")
    else:
        raise FileNotFoundError("zpub.json not found. Please make sure the file exists.")
zpub = load_zpub()

# ==========================
# Bitcoin Address Generation using BIP84 (Mainnet, Bech32)
# ==========================
# Initialize from zpub (use Bip84 class to derive public key from zpub)
bip84_ctx = Bip84.FromExtendedKey(zpub, Bip84Coins.BITCOIN)

# ==========================
# Function to generate all used addresses from zpub
# ==========================
def generate_used_addresses(bip84_ctx, max_addresses=12):
    addresses = []
    for i in range(max_addresses):
        address_ctx = bip84_ctx.Change(Bip44Changes.CHAIN_EXT).AddressIndex(i)
        addresses.append(address_ctx.PublicKey().ToAddress())
    return addresses

# Generate all used addresses
used_addresses = generate_used_addresses(bip84_ctx)

# ==========================
# Fetching Bitcoin UTXOs from Blockstream API
# ==========================
def get_utxos_blockstream(address):
    url = f"https://blockstream.info/api/address/{address}/utxo"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()  # Return the UTXO set for the address
    else:
        print(f"Error fetching UTXOs for {address}. HTTP Status: {response.status_code}")
        return None

# ==========================
# Fetching Bitcoin Balance using Blockstream API
# ==========================
def get_balance_blockstream(address):
    url = f"https://blockstream.info/api/address/{address}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        # Combine confirmed and pending balances
        confirmed_balance_satoshis = data.get('chain_stats', {}).get('funded_txo_sum', 0) - \
                                     data.get('chain_stats', {}).get('spent_txo_sum', 0)
        pending_balance_satoshis = data.get('mempool_stats', {}).get('funded_txo_sum', 0) - \
                                   data.get('mempool_stats', {}).get('spent_txo_sum', 0)
        total_balance_satoshis = confirmed_balance_satoshis + pending_balance_satoshis
        return total_balance_satoshis
    else:
        print(f"Error fetching balance for {address}. HTTP Status: {response.status_code}")
        return None

# ==========================
# Fetching Bitcoin Transaction Data from Blockstream API
# ==========================
def get_transaction_data(txid):
    url = f"https://blockstream.info/api/tx/{txid}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()  # Return the transaction data
    else:
        print(f"Error fetching transaction data for {txid}. HTTP Status: {response.status_code}")
        return None

# ==========================
# Collect all UTXOs from all used addresses (from break_piggy.py)
# ==========================
def collect_all_utxos(addresses):
    all_utxos = []
    total_input_satoshis = 0

    for address in addresses:
        utxos = get_utxos_blockstream(address)
        if utxos:
            for utxo in utxos:
                tx_data = get_transaction_data(utxo['txid'])
                if not tx_data:
                    continue
                vout = tx_data['vout'][utxo['vout']]
                scriptpubkey = vout['scriptpubkey']

                all_utxos.append({
                    "txid": utxo['txid'],
                    "vout": utxo['vout'],
                    "satoshis": utxo['value'],
                    "scriptPubKey": scriptpubkey,
                })
                total_input_satoshis += utxo['value']
    return all_utxos, total_input_satoshis

# ==========================
# Calculate the exact fee based on transaction size
# ==========================
def calculate_fee(unsigned_tx, fee_rate):
    # Serialize the transaction and get the exact byte size
    tx_size = len(unsigned_tx.serialize())  # Get the actual size of the transaction in bytes

    # Calculate the fee based on the actual size and fee rate (in satoshis per byte)
    fee = tx_size * fee_rate
    return fee

# ==========================
# Function to fetch the current fee rate
# ==========================
def fetch_fee_rate():
    url = "https://mempool.space/api/v1/fees/recommended"
    response = requests.get(url)

    if response.status_code == 200:
        fee_data = response.json()
        return fee_data['fastestFee']  # Get the fastest fee rate
    else:
        print(f"Error fetching fee rate. HTTP Status: {response.status_code}")
        return 10  # Fallback to a default fee rate if API fails

# ==========================
# Create PSBT consolidating all UTXOs into a single recipient address
# ==========================
def create_consolidation_psbt(utxos, recipient_address, fee_rate):
    unsigned_tx = CMutableTransaction()  # Create a mutable transaction
    psbt = PartiallySignedTransaction()  # Create the PSBT

    # Add inputs to the PSBT
    for utxo in utxos:
        outpoint = COutPoint(lx(utxo['txid']), utxo['vout'])
        tx_in = CTxIn(outpoint)
        unsigned_tx.vin.append(tx_in)

        psbt_input = PSBT_Input()
        witness_utxo = CTxOut(utxo['satoshis'], CScript(lx(utxo['scriptPubKey'])))
        psbt_input._witness_utxo = witness_utxo
        psbt.add_input(tx_in, psbt_input)

    # Calculate fee based on transaction size
    fee = calculate_fee(unsigned_tx, fee_rate)
    output_value = sum(utxo['satoshis'] for utxo in utxos) - fee

    # Create the recipient output
    recipient_script = CCoinAddress(recipient_address).to_scriptPubKey()
    tx_out = CTxOut(output_value, recipient_script)
    unsigned_tx.vout.append(tx_out)

    # Add the output to the PSBT
    psbt_output = PSBT_Output()
    psbt.add_output(tx_out, psbt_output)  # Pass both tx_out and psbt_output

    # Synchronize the PSBT with the unsigned transaction
    psbt.unsigned_tx = unsigned_tx
    return psbt

# Function to split the PSBT into chunks
def split_data(data, chunk_size):
    return [data[i:i + chunk_size] for i in range(0, len(data), chunk_size)]

# Display multiple QR codes (animated) for PSBT on e-ink display
def display_animated_qr_on_eink(psbt, total_satoshis, fee, num_addresses, recipient_address):
    epd = epd2in13_V4.EPD()
    epd.init()
    epd.Clear(0xFF)

    # Convert PSBT to Base64
    psbt_serialized_base64 = base64.b64encode(psbt.serialize()).decode('utf-8')
    print('Printing PSBT serialized in Base64')
    print(psbt_serialized_base64)

    # Split the PSBT into chunks for the QR code
    chunk_size = 200  # Adjust chunk size based on QR code capacity, set to 200 for smaller chunks
    psbt_chunks = split_data(psbt_serialized_base64, chunk_size)

    # Loop indefinitely to keep showing QR code chunks
    while True:
        for idx, chunk in enumerate(psbt_chunks):
            eink_image = Image.new('1', (epd.height, epd.width), 255)  # Create a blank white image
            draw = ImageDraw.Draw(eink_image)
            font = ImageFont.load_default()

            # Generate QR code for the chunk
            qr = qrcode.QRCode(box_size=2, border=1)
            qr.add_data(chunk)
            qr.make(fit=True)

            # Resize QR code to fit the e-ink screen
            qr_image = qr.make_image(fill='black', back_color='white').resize((120, 120))  # Adjust size to fit
            eink_image.paste(qr_image, (3, 3))  # Position QR code on the display

            # Display additional information and part number
            draw.text((140, 10), f"Part {idx + 1}/{len(psbt_chunks)}", font=font, fill=0)
            draw.text((140, 30), f"Total: {total_satoshis} sats", font=font, fill=0)
            draw.text((140, 50), f"Fee: {fee} sats", font=font, fill=0)
            draw.text((140, 70), f"To: {recipient_address[:17]}...", font=font, fill=0)

            # Display the image on the e-ink display
            eink_image_rotated = eink_image.rotate(90, expand=True)  # Rotate for proper orientation
            epd.display(epd.getbuffer(eink_image_rotated))  # Display image on e-ink

            # Wait for 5 seconds before showing the next QR code
            time.sleep(5)

        # Optionally add a delay before restarting the QR code sequence
        # time.sleep(10)  # Wait 10 seconds before cycling through the QR codes again

    epd.sleep()

# ==========================
# Main function to generate PSBT and display on e-ink
# ==========================
def main():
    if len(sys.argv) < 2:
        print("Usage: python psbt_display.py <recipient_address>")
        sys.exit(1)

    recipient_address = sys.argv[1]
    print(f"Received recipient address: {recipient_address}")

    # Validate recipient address
    try:
        recipient_script = CCoinAddress(recipient_address).to_scriptPubKey()
    except Exception as e:
        print(f"Invalid recipient address: {str(e)}")
        sys.exit(1)

    # Collect UTXOs and generate PSBT
    utxos, total_satoshis = collect_all_utxos(generate_used_addresses(bip84_ctx))
    fee_rate = fetch_fee_rate()
    psbt = create_consolidation_psbt(utxos, recipient_address, fee_rate)
    fee = calculate_fee(psbt.unsigned_tx, fee_rate)

    # Display PSBT on e-ink display
    display_animated_qr_on_eink(psbt, total_satoshis, fee, len(utxos), recipient_address)

if __name__ == "__main__":
    main()
