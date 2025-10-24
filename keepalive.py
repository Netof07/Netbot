from flask import Flask
import threading, requests, time

app = Flask('')

@app.route('/')
def home():
    return "I'm alive"

@app.route('/health')
def health():
    return "OK", 200

def run():
    app.run(host='0.0.0.0', port=8080)

def ping_self():
    while True:
        try:
            # kendi render adresini buraya yaz
            requests.get("https://netbot-ivab.onrender.com/health")
        except:
            pass
        time.sleep(600)  # 10 dakikada bir kendine ping atar

def keep_alive():
    t = threading.Thread(target=run)
    t.start()
    threading.Thread(target=ping_self, daemon=True).start()
