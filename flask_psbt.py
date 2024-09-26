from flask import Flask, request, render_template
import subprocess

app = Flask(__name__)

# ======= Route to show form and collect recipient address ======= #
@app.route('/')
def home():
    return render_template('index.html')

# Route to handle PSBT generation
@app.route('/generate_psbt', methods=['POST'])
def generate_psbt():
    # Get recipient address from the form
    recipient_address = request.form.get('recipient_address')

    # Validate recipient address
    if not recipient_address:
        return render_template('index.html', error="Recipient address is required")

    # Call the PSBT display script using subprocess
    try:
        # Using subprocess to call the psbt_display.py script and passing recipient_address as an argument
        subprocess.Popen(['python3', 'psbt.py', recipient_address])
        return render_template('index.html', message="PSBT is being displayed on the e-ink screen!")
    except Exception as e:
        return render_template('index.html', error=f"Failed to display PSBT: {str(e)}")

# Start the Flask app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
