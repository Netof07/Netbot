import os
import time
import logging
import threading
from datetime import datetime, timezone
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Environment / config
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
BASE_URL = os.getenv("BASE_URL", "https://api.binance.com/api/v3")
ALERT_MULTIPLIER = float(os.getenv("ALERT_MULTIPLIER", "5"))  # 5x by default
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))  # default hourly
FLASK_PORT = int(os.getenv("PORT", "10000"))

if not TG_TOKEN or not TG_CHAT_ID:
    logging.warning("TG_TOKEN or TG_CHAT_ID not set. Add them to environment variables.")

try:
    TG_CHAT_ID = int(TG_CHAT_ID) if TG_CHAT_ID is not None else None
except Exception:
    logging.exception("TG_CHAT_ID could not be converted to int. Check value.")
    TG_CHAT_ID = None

# Telegram send via requests (no external telegram lib required)
def send_telegram(text):
    if not TG_TOKEN or not TG_CHAT_ID:
        logging.warning("Skipping Telegram send: token or chat id missing.")
        return False
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {"chat_id": str(TG_CHAT_ID), "text": text}
        resp = requests.post(url, data=payload, timeout=10)
        if resp.status_code != 200:
            logging.warning(f"Telegram returned status {resp.status_code}: {resp.text}")
            return False
        return True
    except Exception:
        logging.exception("Failed to send Telegram message:")
        return False

# Flask app for Render healthcheck / uptime
app = Flask(__name__)
last_run_time = None
last_alerts = []

@app.route("/")
def home():
    return jsonify({
        "status": "NetBot running",
        "last_run": last_run_time.isoformat() if last_run_time else None,
        "recent_alerts": last_alerts[-10:]
    })

# Helper: get active USDT spot symbols
def get_active_symbols():
    try:
        url = f"{BASE_URL}/exchangeInfo"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        symbols = []
        for s in data.get("symbols", []):
            perms = s.get("permissions") or []
            if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT":
                if perms:
                    if "SPOT" in perms:
                        symbols.append(s["symbol"])
                else:
                    symbols.append(s["symbol"])
        logging.info(f"Fetched {len(symbols)} active USDT symbols")
        return symbols
    except Exception:
        logging.exception("Failed to fetch exchangeInfo")
        return []

# Track which candle has already alerted to avoid duplicates
alerted_keys = set()

def check_volume(interval):
    global last_run_time, last_alerts
    logging.info(f"Checking volumes for interval: {interval}")
    symbols = get_active_symbols()
    alerts = []
    session = requests.Session()
    session.headers.update({"User-Agent": "netbot/1.0"})
    for symbol in symbols:
        try:
            params = {"symbol": symbol, "interval": interval, "limit": 2}
            r = session.get(f"{BASE_URL}/klines", params=params, timeout=12)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, list) or len(data) < 2:
                continue
            prev_volume = float(data[-2][5]) if data[-2][5] else 0.0
            last_volume = float(data[-1][5]) if data[-1][5] else 0.0
            last_open = int(data[-1][0])  # open time in ms

            # skip if previous volume is zero (avoid div by zero and noisy alerts)
            if prev_volume == 0:
                continue

            if last_volume >= prev_volume * ALERT_MULTIPLIER:
                key = f"{symbol}:{interval}:{last_open}"
                if key in alerted_keys:
                    continue
                ratio = last_volume / prev_volume if prev_volume else 0
                ts = datetime.fromtimestamp(last_open/1000, tz=timezone.utc)
                msg = (
                    f"🔥 {symbol} hacmi {interval} periyotta *{ratio:.2f}x* arttı!\n"
                    f"⏱ Candle start (UTC): {ts.isoformat(sep=' ')}\n"
                    f"📉 Önceki hacim: {prev_volume:,.0f}\n"
                    f"📈 Şimdi: {last_volume:,.0f}"
                )
                alerts.append((symbol, msg))
                alerted_keys.add(key)
        except Exception:
            logging.exception(f"Error checking {symbol} {interval}")
        time.sleep(0.01)

    for symbol, message in alerts:
        ok = send_telegram(message)
        if ok:
            logging.info(f"Alert sent for {symbol} {interval}")
            last_alerts.append({"symbol": symbol, "interval": interval, "time": datetime.now(timezone.utc).isoformat()})
            time.sleep(0.4)
    last_run_time = datetime.now(timezone.utc)

def job():
    try:
        check_volume("4h")
        check_volume("1d")
    except Exception:
        logging.exception("Job failed")

def start_scheduler():
    logging.info("Starting scheduler (runs every %s minutes)", CHECK_INTERVAL_MINUTES)
    job()
    scheduler = BackgroundScheduler()
    scheduler.add_job(job, "interval", minutes=CHECK_INTERVAL_MINUTES)
    scheduler.start()

if __name__ == "__main__":
    send_telegram("🚀 NetBot başlatıldı — 4h & 1d tarama (5x filtre).")
    t = threading.Thread(target=start_scheduler, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=FLASK_PORT)
