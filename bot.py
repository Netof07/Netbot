import os
import time
import requests
from keepalive import keep_alive
from datetime import datetime

TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")

CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", 60))
VOLUME_MULTIPLIER = float(os.getenv("VOLUME_MULTIPLIER", 5))

def send_message(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text}
        )
    except Exception as e:
        print("Mesaj gönderilemedi:", e)

def get_binance_data(symbol="BTCUSDT", interval="4h"):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=2"
    data = requests.get(url).json()
    if len(data) < 2:
        return None
    prev_vol = float(data[-2][5])
    curr_vol = float(data[-1][5])
    return prev_vol, curr_vol

def main_loop():
    send_message("✅ NetBot başlatıldı. Otomatik tarama aktif (UptimeRobot destekli).")
    while True:
        try:
            for symbol in ["BTCUSDT", "ETHUSDT", "BNBUSDT"]:
                prev_vol, curr_vol = get_binance_data(symbol)
                ratio = curr_vol / prev_vol if prev_vol else 0
                if ratio >= VOLUME_MULTIPLIER:
                    msg = f"🚀 {symbol} hacim farkı {ratio:.2f}x (4h)"
                    send_message(msg)
                    print(msg)
                else:
                    print(f"{symbol}: {ratio:.2f}x")
        except Exception as e:
            print("Hata:", e)
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    keep_alive()
    main_loop()
