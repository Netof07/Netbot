import time
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot
import os

# Telegram bilgileri (Render'da .env'den alınacak)
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
bot = Bot(token=TG_TOKEN)

# Binance API
BASE_URL = "https://api.binance.com/api/v3"

# Önceki hacimleri saklayacak
previous_volumes = {}

def get_symbols():
    url = f"{BASE_URL}/exchangeInfo"
    resp = requests.get(url).json()
    symbols = [s["symbol"] for s in resp["symbols"] if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"]
    return symbols

def check_volume(interval):
    symbols = get_symbols()
    for symbol in symbols:
        url = f"{BASE_URL}/klines?symbol={symbol}&interval={interval}&limit=2"
        data = requests.get(url).json()
        if len(data) < 2:
            continue
        prev_volume = float(data[-2][5])
        last_volume = float(data[-1][5])
        if symbol not in previous_volumes:
            previous_volumes[symbol] = prev_volume
        # 🔹 Burada 5x kontrol var (artık 3x değil!)
        if last_volume >= previous_volumes[symbol] * 5:
            msg = f"⚡ {symbol} hacmi {interval} aralığında 5 kat arttı!\nÖnceki: {previous_volumes[symbol]:,.0f}, Şimdi: {last_volume:,.0f}"
            bot.send_message(chat_id=TG_CHAT_ID, text=msg)
        previous_volumes[symbol] = last_volume

def job():
    check_volume("4h")
    check_volume("1d")

if __name__ == "__main__":
    print("✅ Bot çalışıyor... 1d ve 4h hacimleri kontrol edecek.")
    bot.send_message(chat_id=TG_CHAT_ID, text="✅ Bot başarıyla çalışıyor!")
    scheduler = BackgroundScheduler()
    scheduler.add_job(job, 'interval', minutes=60)  # her 1 saatte kontrol
    scheduler.start()
    while True:
        time.sleep(10)
