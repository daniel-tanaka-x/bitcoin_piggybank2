import os
import json
import requests
import ccxt
import pandas as pd
import talib
import yfinance as yf
from datetime import datetime, timedelta
from bip_utils import Bip84, Bip84Coins, Bip44Changes

# ==========================
# Configuration Constants
# ==========================
BUY_AMOUNT = 30  # Amount in USD to buy
BTC_THRESHOLD = 90  # Threshold in USD to withdraw
RSI_PERIOD = 14

# ==========================
# Helper Functions
# ==========================
def load_json(file_or_url):
    """Load JSON data from a file or URL."""
    if os.path.exists(file_or_url):
        with open(file_or_url, 'r') as f:
            return json.load(f)
    response = requests.get(file_or_url)
    if response.status_code == 200:
        return response.json()
    raise ValueError(f"Failed to load data from {file_or_url}")


def fetch_utxos(address):
    """Fetch UTXOs for a given Bitcoin address."""
    url = f"https://blockstream.info/api/address/{address}/utxo"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return []


def generate_first_address(zpub):
    """Generate the first Bitcoin address from a given zpub using BIP84 (index 0)."""
    bip84_ctx = Bip84.FromExtendedKey(zpub, Bip84Coins.BITCOIN)
    return bip84_ctx.Change(Bip44Changes.CHAIN_EXT).AddressIndex(0).PublicKey().ToAddress()


def fetch_rsi_signals(btc_data, rsi_period):
    """Fetch RSI signals over the last 38 hours of Bitcoin data."""
    last_24_hours = btc_data.tail(38)
    last_24_hours['RSI'] = talib.RSI(last_24_hours['Close'], timeperiod=rsi_period)
    buy_signals = last_24_hours[last_24_hours['RSI'] < 20]
    print(f"RSI values for the last 24 hours:\n{last_24_hours['RSI']}")
    print(f"Buy signals (RSI < 20) found: {len(buy_signals)}")
    return len(buy_signals)


def fetch_fear_and_greed_index():
    """Fetch the Fear and Greed Index and check for extreme fear."""
    fng_data = load_json("https://api.alternative.me/fng/?limit=1")['data'][0]
    fng_value = int(fng_data['value'])
    print(f"Fear and Greed Index: {fng_value}, Extreme fear: {fng_value <= 25}")
    return fng_value <= 25


def find_best_exchange_for_btc(exchanges):
    """Find the best exchange to buy BTC based on the lowest BTC/USDT price."""
    best_price = float('inf')
    best_exchange = None

    for exchange_name, exchange in exchanges.items():
        try:
            if not exchange.apiKey or not exchange.secret:
                print(f"Skipping {exchange_name} due to missing API credentials.")
                continue

            ticker = exchange.fetch_ticker('BTC/USDT')
            price = ticker['last']
            print(f"{exchange_name} offers BTC/USDT at {price} USD")

            if price < best_price:
                best_price = price
                best_exchange = exchange_name

        except Exception as e:
            print(f"Failed to fetch ticker from {exchange_name}: {e}")

    if best_exchange:
        print(f"Best exchange to buy BTC: {best_exchange} at {best_price} USD")
    return best_exchange, best_price


def execute_buy_order(exchange, buy_amount, best_price):
    """Execute a market buy order for BTC/USDT."""
    try:
        balance = exchange.fetch_balance()['total'].get('USDT', 0)
        print(f"Balance on exchange: {balance} USDT")

        if balance >= buy_amount:
            symbol = 'BTC/USDT'
            order = exchange.create_market_buy_order(symbol, buy_amount / best_price)
            print(f"Bought {buy_amount} USD worth of BTC on exchange")
        else:
            print(f"Insufficient balance to buy BTC.")
    except Exception as e:
        print(f"Failed to buy BTC: {e}")


def check_and_withdraw_btc(exchanges, first_address, btc_threshold):
    """Check balances and withdraw BTC if the value exceeds a threshold."""
    for exchange_name, exchange in exchanges.items():
        try:
            if not exchange.apiKey or not exchange.secret:
                print(f"Skipping {exchange_name} due to missing API credentials.")
                continue

            # Fetch BTC balance
            btc_balance = exchange.fetch_balance()['total'].get('BTC', 0)
            btc_price = exchange.fetch_ticker('BTC/USDT')['last']
            btc_value = btc_balance * btc_price

            print(f"BTC balance on {exchange_name}: {btc_balance}, valued at {btc_value} USD")

            # Check if BTC value exceeds the threshold for withdrawal
            if btc_value >= btc_threshold:
                print(f"Using the first Bitcoin address for withdrawal: {first_address}")

                # Set up withdrawal parameters for specific exchanges
                withdrawal_params = {}
                if exchange_name == 'bybit':
                    withdrawal_params = {'chain': 'BTC'}
                elif exchange_name == 'bitget':
                    withdrawal_params = {'chain': 'BTC'}
                elif exchange_name == 'kucoin':
                    withdrawal_params = {'network': 'BTC'}
                elif exchange_name == 'mexc':
                    withdrawal_params = {'chain': 'BTC'}

                print(f"Attempting to withdraw from {exchange_name}...")
                print(f"BTC Balance: {btc_balance}, Address: {first_address}, Params: {withdrawal_params}")

                # Execute the withdrawal
                try:
                    withdrawal = exchange.withdraw('BTC', btc_balance, first_address, None, withdrawal_params)
                    print(f"Withdrew {btc_balance} BTC from {exchange_name} to {first_address}")
                except Exception as e:
                    print(f"Failed to withdraw from {exchange_name}: {e}")
            else:
                print(f"BTC value on {exchange_name} is below the threshold for withdrawal: {btc_value} USD")
        except Exception as e:
            print(f"Failed to fetch balance on {exchange_name}: {e}")


# ==========================
# Main Bot Logic
# ==========================
def main():
    # Load API keys and zpub from JSON files
    api_keys = load_json("api_keys.json")
    zpub = load_json("zpub.json").get("zpub")

    # Generate the first Bitcoin address from zpub
    first_address = generate_first_address(zpub)
    print(f"Your first Bitcoin address: {first_address}")
    print("Please register this address on the following exchanges:")
    print("- Bybit")
    print("- Bitget")
    print("- Kucoin")
    print("- MEXC")

    # Setup exchange credentials
    EXCHANGES = {
        'bybit': ccxt.bybit({'apiKey': api_keys.get('bybit', {}).get('apiKey'), 'secret': api_keys.get('bybit', {}).get('secret')}),
        'bitget': ccxt.bitget({'apiKey': api_keys.get('bitget', {}).get('apiKey'), 'secret': api_keys.get('bitget', {}).get('secret'), 'password': api_keys.get('bitget', {}).get('password')}),
        'kucoin': ccxt.kucoin({'apiKey': api_keys.get('kucoin', {}).get('apiKey'), 'secret': api_keys.get('kucoin', {}).get('secret'), 'password': api_keys.get('kucoin', {}).get('password')}),
        'mexc': ccxt.mexc({'apiKey': api_keys.get('mexc', {}).get('apiKey'), 'secret': api_keys.get('mexc', {}).get('secret')}),
    }

    # Fetch Bitcoin price data for the last 5 days
    end_date = datetime.today()
    start_date = end_date - timedelta(days=5)
    btc = yf.download('BTC-USD', start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), interval='1h')
    btc.index = btc.index.tz_convert('UTC')

    # Fetch RSI signals for the last 24 hours
    buy_signals = fetch_rsi_signals(btc, RSI_PERIOD)

    # Check the Fear and Greed Index
    extreme_fear = fetch_fear_and_greed_index()

    # Determine if a buy order should be placed
    if buy_signals > 0 or extreme_fear:
        best_exchange, best_price = find_best_exchange_for_btc(EXCHANGES)
        if best_exchange:
            execute_buy_order(EXCHANGES[best_exchange], BUY_AMOUNT, best_price)

    # Withdraw BTC if the balance exceeds the threshold
    check_and_withdraw_btc(EXCHANGES, first_address, BTC_THRESHOLD)


if __name__ == "__main__":
    main()
