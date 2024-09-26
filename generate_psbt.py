#!/usr/bin/python
# -*- coding:utf-8 -*-
import os
import sys
import json
import base64
import requests
from bip_utils import Bip84, Bip84Coins, Bip44Changes
from bitcointx.wallet import CCoinAddress
from bitcointx.core import COutPoint, lx, CTxIn, CTxOut, CMutableTransaction
from bitcointx.core.psbt import PartiallySignedTransaction, PSBT_Input, PSBT_Output
from bitcointx.core.script import CScript

# ==========================
# Load zpub from file
# ==========================
def load_zpub():
    zpub_file = "zpub.json"
    if os.path.exists(zpub_file):
        with open(zpub_file, 'r') as f:
            data = json.load(f)
            return data.get("zpub")
    else:
        raise FileNotFoundError("zpub.json not found. Please make sure the file exists.")

zpub = load_zpub()

# Initialize Bip84 context
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

# ==========================
# Fetching Bitcoin UTXOs from Blockstream API
# ==========================
def get_utxos_blockstream(address):
    url = f"https://blockstream.info/api/address/{address}/utxo"
    response = requests.get(url)  # SSL verification is enabled by default
    return response.json() if response.status_code == 200 else None

# ==========================
# Fetch Transaction Details from Blockstream API to get scriptPubKey
# ==========================
def get_tx_details_blockstream(txid):
    url = f"https://blockstream.info/api/tx/{txid}"
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

# ==========================
# Collect all UTXOs from all used addresses and fetch scriptPubKey
# ==========================
def collect_all_utxos(addresses):
    all_utxos = []
    total_input_satoshis = 0

    for address in addresses:
        utxos = get_utxos_blockstream(address)
        if utxos:
            for utxo in utxos:
                # Fetch full transaction details to get scriptPubKey
                tx_details = get_tx_details_blockstream(utxo['txid'])
                if tx_details:
                    # Get the specific vout corresponding to the UTXO
                    vout = tx_details['vout'][utxo['vout']]
                    utxo['scriptPubKey'] = vout['scriptpubkey']  # Add scriptPubKey to UTXO data
                    all_utxos.append(utxo)
                    total_input_satoshis += utxo['value']
    return all_utxos, total_input_satoshis

# ==========================
# Create PSBT consolidating all UTXOs into a single recipient address
# ==========================
def create_consolidation_psbt(utxos, recipient_address, fee_rate):
    unsigned_tx = CMutableTransaction()
    psbt = PartiallySignedTransaction()

    for utxo in utxos:
        outpoint = COutPoint(lx(utxo['txid']), utxo['vout'])
        tx_in = CTxIn(outpoint)
        unsigned_tx.vin.append(tx_in)

        psbt_input = PSBT_Input()
        # Now we have scriptPubKey from the UTXO
        witness_utxo = CTxOut(utxo['value'], CScript(lx(utxo['scriptPubKey'])))
        psbt_input._witness_utxo = witness_utxo
        psbt.add_input(tx_in, psbt_input)

    fee = calculate_fee(unsigned_tx, fee_rate)
    output_value = sum(utxo['value'] for utxo in utxos) - fee

    recipient_script = CCoinAddress(recipient_address).to_scriptPubKey()
    tx_out = CTxOut(output_value, recipient_script)
    unsigned_tx.vout.append(tx_out)

    psbt_output = PSBT_Output()
    psbt.add_output(tx_out, psbt_output)
    psbt.unsigned_tx = unsigned_tx
    return psbt

# Function to calculate fee based on transaction size and fee rate
def calculate_fee(unsigned_tx, fee_rate):
    tx_size = len(unsigned_tx.serialize())  # Calculate transaction size in bytes
    return tx_size * fee_rate  # Fee in satoshis

# Fetch fee rate from mempool.space API
def fetch_fee_rate():
    url = "https://mempool.space/api/v1/fees/recommended"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json().get('fastestFee', 10)  # Get fastest fee or default to 10 sat/vB
    else:
        raise Exception("Failed to fetch fee rate")

# Main function to generate PSBT and return it
def generate_psbt(recipient_address):
    # 1. Get all UTXOs and total satoshis
    utxos, total_satoshis = collect_all_utxos(generate_used_addresses(bip84_ctx))
    
    # 2. Fetch fee rate from mempool.space
    fee_rate = fetch_fee_rate()
    
    # 3. Generate PSBT
    psbt = create_consolidation_psbt(utxos, recipient_address, fee_rate)
    
    # 4. Calculate fee
    fee = calculate_fee(psbt.unsigned_tx, fee_rate)
    
    # 5. Serialize the PSBT for output
    psbt_serialized = base64.b64encode(psbt.serialize()).decode('utf-8')
    
    # 6. Return the serialized PSBT, total input satoshis, and fee
    return psbt_serialized, total_satoshis, fee

# Main entry point for command line
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate_psbt.py <recipient_address>")
        sys.exit(1)

    recipient_address = sys.argv[1]
    
    # Generate the PSBT, total satoshis, and fee
    try:
        psbt_data, total_satoshis, fee = generate_psbt(recipient_address)
        
        # Output all 3 values separated by newlines for Flask app to capture
        print(psbt_data)
        print(total_satoshis)
        print(fee)
    
    except Exception as e:
        print(f"Failed to generate PSBT: {str(e)}")
        sys.exit(1)
