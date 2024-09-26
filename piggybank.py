#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys, os, logging, platform, time, requests, json
from waveshare_epd import epd2in13_V4  # Import the Waveshare E-Ink display driver
from PIL import Image, ImageDraw, ImageFont
from bip_utils import Bip84, Bip84Coins, Bip44Changes
import qrcode

# Initialize paths, logging, and display driver
picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir): sys.path.append(libdir)

logging.basicConfig(level=logging.DEBUG)
time.sleep(30)  # Delay before fetching data

# ==========================
# Helper Functions
# ==========================
def load_json(file):
    if os.path.exists(file):
        with open(file, 'r') as f:
            return json.load(f)
    raise FileNotFoundError(f"{file} not found. Please make sure the file exists.")

def api_get(url):
    response = requests.get(url)
    return response.json() if response.status_code == 200 else None

# ==========================
# Bitcoin Functions
# ==========================
def get_utxos(address): 
    return api_get(f"https://blockstream.info/api/address/{address}/utxo")

def get_balance(address):
    data = api_get(f"https://blockstream.info/api/address/{address}")
    if data:
        balance = data.get('chain_stats', {}).get('funded_txo_sum', 0) - data.get('chain_stats', {}).get('spent_txo_sum', 0)
        mempool_balance = data.get('mempool_stats', {}).get('funded_txo_sum', 0) - data.get('mempool_stats', {}).get('spent_txo_sum', 0)
        return balance + mempool_balance
    return None

def collect_utxos(addresses):
    all_utxos, total_satoshis, utxo_count = [], 0, 0
    for address in addresses:
        utxos = get_utxos(address)
        if utxos:
            for utxo in utxos:
                all_utxos.append(utxo)
                total_satoshis += utxo['value']
                utxo_count += 1  # Count the UTXOs
    return all_utxos, total_satoshis, utxo_count

# ==========================
# Display Functions
# ==========================
def display_text(draw, font, total_satoshis):
    draw.text((10, 10), "I'm full! Break me to take out sats", font=font, fill=0)
    draw.text((10, 30), "Total Balance:", font=font, fill=0)
    draw.text((10, 50), f"{total_satoshis} satoshi", font=font, fill=0)
    draw.text((10, 80), "Please use your seed directly.", font=font, fill=0)
    draw.text((10, 95), "I'm really proud of you. Good job!", font=font, fill=0)

def display_full_status(total_satoshis):
    epd = epd2in13_V4.EPD()
    epd.init(), epd.Clear(0xFF)
    eink_image = Image.new('1', (epd.height, epd.width), 255)
    draw = ImageDraw.Draw(eink_image)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 12)
    display_text(draw, font, total_satoshis)
    epd.display(epd.getbuffer(eink_image.rotate(90, expand=True)))
    epd.sleep()

def display_on_eink(index, balance, addr, utxo_count):
    epd = epd2in13_V4.EPD()
    epd.init(), epd.Clear(0xFF)
    img = Image.new('1', (epd.height, epd.width), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 11)

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=3, border=1)
    qr.add_data(addr), qr.make(fit=True)
    qr_img = qr.make_image(fill="black", back_color="white").resize((100, 100))
    img.paste(qr_img, (5, 10))

    draw.text((110, 10), "Bitcoin PiggyBank", font=font, fill=0)
    draw.text((110, 40), "Total Balance:", font=font, fill=0)
    draw.text((110, 60), f"{balance} sats", font=font, fill=0)
    draw.text((110, 90), f"You saved {utxo_count} times!", font=font, fill=0)

    epd.display(epd.getbuffer(img.rotate(90, expand=True)))
    epd.sleep()

# ==========================
# Main Execution Loop
# ==========================
zpub = load_json("zpub.json").get("zpub")
bip84_ctx = Bip84.FromExtendedKey(zpub, Bip84Coins.BITCOIN)
addresses = [bip84_ctx.Change(Bip44Changes.CHAIN_EXT).AddressIndex(i).PublicKey().ToAddress() for i in range(21)]

while True:
    total_balance, found_unused, utxo_count, i = 0, False, 0, 0

    while not found_unused:
        addr = addresses[i]
        balance = get_balance(addr)
        print(f"Checking address {i}: {addr}, Balance: {balance} sats")

        if balance is None:
            print(f"Skipping address {i} due to rate limit.")
            continue

        if balance == 0 and not found_unused:
            found_unused, current_index = True, i

        if balance > 0:
            total_balance += balance
            utxos = get_utxos(addr)
            utxo_count += len(utxos)  # Count UTXOs for each address

        i += 1

    display_on_eink(current_index, total_balance, addr, utxo_count)
    print(f"Unused address: {addr} (Index: {current_index})")
    print(f"Total Balance: {total_balance} sats")
    print(f"Total UTXOs (Savings): {utxo_count}")

    if utxo_count >= 21:  # Break piggybank when 21 UTXOs are saved
        print("Used UTXOs Count reached 21. Initiating break.")
        utxos, total_satoshis, total_utxo_count = collect_utxos(addresses)
        display_full_status(total_satoshis)
        break

    time.sleep(30)
