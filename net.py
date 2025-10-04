import time
import requests
import pytz
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from telegram import Bot
from flask import Flask

# Flask sunucusu (Render'da servis canlı kalması için)
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Volume bot aktif - Binance API (Europe) sürümü çalışıyor."

# Telegram bilgileri
TG_TOKEN = "YOUR_TG_TOKEN_HERE"  # .env'den okunabilir
TG_CHAT_ID = "YOUR_CHAT_ID_HERE"

bot = Bot(token=TG_TOKEN)

# Binance API (Europe domain - 451 hatası çözülür)
BASE_URL = "https://api.binance.me/api/v3"

# Önceki hacimleri saklayacak
previous_volumes = {}

# Kaç kat artışta bildirim göndersin (5x)
VOLUME_MULTIPLIER = 5

# Kaç dakikada bir çalışsın (Render'da 60 dk ideal)
CHECK_INTERVAL_MINUTES = 60


def get_active_symbols():
    """Aktif işlem gören USDT paritelerini döndürür"""
    url = f"{BASE_URL}/exchangeInfo"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        symbols = [
            s["symbol"] for s in data["symbols"]
            if s["quoteAsset"] == "USDT" and s["status"] == "TRADING"
        ]
        return symbols
    except Exception as e:
        print("Failed to fetch exchangeInfo:", e)
        return []


def check_volume(interval):
    """Belirli zaman aralığında hacim artışlarını kontrol eder"""
    print(f"[{datetime.now()}] Checking volumes for interval: {interval}")
    symbols = get_active_symbols()
    for symbol in symbols:
        try:
            url = f"{BASE_URL}/klines?symbol={symbol}&interval={interval}&limit=2"
            data = requests.get(url, timeout=10).json()

            if len(data) < 2:
                continue

            prev_volume = float(data[-2][5])
            last_volume = float(data[-1][5])

            if symbol not in previous_volumes:
                previous_volumes[symbol] = prev_volume

            # 5x artış kontrolü
            if last_volume >= previous_volumes[symbol] * VOLUME_MULTIPLIER:
                msg = (
                    f"⚡ {symbol} hacmi {interval} aralığında {VOLUME_MULTIPLIER} kat arttı!\n"
                    f"Önceki: {previous_volumes[symbol]:,.0f}, Şimdi: {last_volume:,.0f}"
                )
                bot.send_message(chat_id=TG_CHAT_ID, text=msg)

            previous_volumes[symbol] = last_volume
        except Exception as e:
            print(f"Error checking {symbol}: {e}")


def job():
    check_volume("4h")
    check_volume("1d")


def start_scheduler():
    """Arka planda çalışan zamanlayıcı"""
    scheduler = BackgroundScheduler(timezone=pytz.timezone("Europe/Istanbul"))
    scheduler.add_job(job, "interval", minutes=CHECK_INTERVAL_MINUTES)
    scheduler.start()
    print(f"[INFO] Starting scheduler (runs every {CHECK_INTERVAL_MINUTES} minutes)")


if __name__ == "__main__":
    print("✅ Bot başlatılıyor...")
    try:
        bot.send_message(chat_id=TG_CHAT_ID, text="✅ Volume Bot başarıyla başlatıldı! (Yeni sürüm)")
    except Exception as e:
        print("Telegram bağlantısı başarısız:", e)

    start_scheduler()

    # Flask keep-alive
    app.run(host="0.0.0.0", port=10000)
