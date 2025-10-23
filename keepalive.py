from flask import Flask
import threading
import os

app = Flask('keepalive')

@app.route('/')
def home():
    return '✅ NetBot keepalive OK', 200

def _run():
    # Note: this is a development server used for keepalive only.
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def start_keepalive_thread():
    t = threading.Thread(target=_run, daemon=True)
    t.start()
