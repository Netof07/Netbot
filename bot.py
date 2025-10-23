import os
import time
import requests
from dotenv import load_dotenv
from keepalive import keep_alive

# .env dosyasını yükle
load_dotenv()

TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", 60))
VOLUME_MULTIPLIER = float(os.getenv("VOLUME_MULTIPLIER", 5))

def send_message(text):
    """Telegram'a mesaj gönderir."""
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                          json={"chat_id": CHAT_ID, "text": text})
        if r.status_code != 200:
            print(f"⚠️ Telegram hatası: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"❌ Mesaj gönderilemedi: {e}")

def main_loop():
    send_message("✅ NetBot başlatıldı. Otomatik tarama aktif.")
    print("NetBot aktif! Kontroller başlıyor...")
    
    while True:
        try:
            print("📊 Kontrol yapılıyor...")
            # Buraya API sorgusu (örnek test verisi)
            fake_signal = "BTCUSDT 5.2x fark tespit edildi!"
            send_message(f"🚀 Yeni sinyal: {fake_signal}")
        except Exception as e:
            print("Hata:", e)
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    keep_alive()
    main_loop()
