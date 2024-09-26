from flask import Flask, request, render_template, jsonify
import subprocess
import os
import json
import base64
import requests
from bitcointx.core.psbt import PartiallySignedTransaction

app = Flask(__name__)

# ======= Route to show form and collect recipient address ======= #
@app.route('/')
def home():
    return render_template('index.html')

# Route to handle PSBT generation
@app.route('/generate_psbt', methods=['POST'])
def generate_psbt():
    recipient_address = request.form.get('recipient_address')

    if not recipient_address:
        return render_template('index.html', error="Recipient address is required")

    try:
        # Call the generate_psbt.py script and capture the output
        process = subprocess.Popen(
            ['python3', 'generate_psbt.py', recipient_address],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        psbt_data, error = process.communicate()

        if process.returncode != 0:
            return render_template('index.html', error=f"Failed to generate PSBT: {error.decode('utf-8')}")

        # The psbt_data should have PSBT, total_satoshis, and fee, separated by newlines
        psbt_data_str = psbt_data.decode('utf-8').strip()
        psbt_serialized, total_satoshis, fee = psbt_data_str.split('\n')

        # Split the PSBT into chunks for QR codes
        chunk_size = 400
        psbt_chunks = [psbt_serialized[i:i + chunk_size] for i in range(0, len(psbt_serialized), chunk_size)]

        # Render the PSBT details page
        return render_template('psbt.html', psbt_serialized=psbt_serialized, total_satoshis=total_satoshis, fee=fee, psbt_chunks=psbt_chunks)

    except Exception as e:
        return render_template('index.html', error=f"Failed to generate PSBT: {str(e)}")

# Route to broadcast signed PSBT
@app.route('/broadcast_psbt', methods=['POST'])
def broadcast_psbt():
    signed_psbt_base64 = request.form.get('signed_psbt')

    if not signed_psbt_base64:
        return jsonify({"error": "No signed PSBT provided"}), 400

    try:
        # Decode and deserialize the signed PSBT
        signed_psbt_bytes = base64.b64decode(signed_psbt_base64)
        signed_psbt = PartiallySignedTransaction.deserialize(signed_psbt_bytes)
        raw_transaction = signed_psbt.tx.serialize().hex()  # Get the final raw transaction

        # Broadcast the transaction using Blockstream API or your preferred Bitcoin node API
        broadcast_url = "https://blockstream.info/api/tx"
        response = requests.post(broadcast_url, data=raw_transaction)

        if response.status_code == 200:
            return jsonify({"message": "Transaction broadcast successfully!"}), 200
        else:
            return jsonify({"error": "Failed to broadcast transaction", "details": response.text}), 400

    except Exception as e:
        return jsonify({"error": f"Failed to decode or broadcast PSBT: {str(e)}"}), 500

# Route to set Wi-Fi credentials
@app.route('/setup_wifi', methods=['POST'])
def setup_wifi():
    ssid = request.form.get('ssid')
    password = request.form.get('password')

    if not ssid or not password:
        return jsonify({"error": "Wi-Fi SSID and password are required"}), 400

    # Call the shell script with sudo to set up Wi-Fi credentials
    try:
        result = subprocess.run(['sudo', '/home/daniel/setup_wifi.sh', ssid, password],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            return jsonify({"error": f"Failed to set Wi-Fi credentials: {result.stderr.decode()}"}), 500

    except Exception as e:
        return jsonify({"error": f"Failed to set Wi-Fi credentials: {str(e)}"}), 500

    return jsonify({"message": "Wi-Fi credentials set successfully! Reconnect to the new Wi-Fi."}), 200
    
# Route to set zpub
@app.route('/setup_zpub', methods=['POST'])
def setup_zpub():
    zpub = request.form.get('zpub')

    if not zpub:
        return jsonify({"error": "zpub key is required"}), 400

    # Set up the zpub in the zpub.json file
    try:
        zpub_data = {"zpub": zpub}
        with open('zpub.json', 'w') as zpub_file:
            json.dump(zpub_data, zpub_file)
    except Exception as e:
        return jsonify({"error": f"Failed to save zpub: {str(e)}"}), 500

    return jsonify({"message": "zpub key set successfully!"}), 200

# Start the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
