import time
import requests
import os
from apscheduler.schedulers.background import BackgroundScheduler

# Telegram bilgileri (Render .env içine ekledin zaten)
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

BASE_URL = "https://api.binance.com/api/v3"

# Önceki hacimleri tutmak için
previous_volumes = {}

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        payload = {"chat_id": TG_CHAT_ID, "text": msg}
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram hata:", e)

def get_symbols():
    """USDT paritelerini çekiyoruz"""
    url = f"{BASE_URL}/exchangeInfo"
    resp = requests.get(url).json()
    symbols = [
        s["symbol"]
        for s in resp["symbols"]
        if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"
    ]
    return symbols

def check_volume(interval):
    """Belirtilen interval için hacim kontrolü"""
    symbols = get_symbols()
    for symbol in symbols:
        url = f"{BASE_URL}/klines?symbol={symbol}&interval={interval}&limit=2"
        data = requests.get(url).json()
        if len(data) < 2:
            continue

        prev_volume = float(data[-2][5])
        last_volume = float(data[-1][5])

        key = f"{symbol}_{interval}"
        if key not in previous_volumes:
            previous_volumes[key] = prev_volume

        # ✅ 5x kontrolü
        if last_volume >= previous_volumes[key] * 5:
            msg = (
                f"⚡ {symbol} hacmi {interval} aralığında 5x arttı!\n"
                f"Önceki: {previous_volumes[key]:,.0f}, Şimdi: {last_volume:,.0f}"
            )
            send_telegram(msg)

        previous_volumes[key] = last_volume

def job():
    check_volume("4h")
    check_volume("1d")

if __name__ == "__main__":
    send_telegram("✅ Bot aktif, 4H & 1D hacim taraması başladı.")

    scheduler = BackgroundScheduler()
    scheduler.add_job(job, "interval", minutes=60)  # her saat kontrol
    scheduler.start()

    # Render'da script ayakta kalsın diye
    while True:
        time.sleep(10)
