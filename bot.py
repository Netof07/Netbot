from keepalive import keep_alive
import os
import time
import requests

# Çevre değişkenleri (Render Environment sekmesinden geliyor)
TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", 60))
VOLUME_MULTIPLIER = float(os.getenv("VOLUME_MULTIPLIER", 5))

def send_message(text):
    """Telegram'a mesaj gönderen fonksiyon"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text}
        )
    except Exception as e:
        print(f"Mesaj gönderilemedi: {e}")

def main_loop():
    """Ana döngü: belirli aralıklarla çalışır"""
    send_message("✅ NetBot başlatıldı. Otomatik tarama aktif.")
    while True:
        try:
            print("Kontrol yapılıyor...")
            # Buraya tarama/analiz kodlarını ekleyeceğiz
        except Exception as e:
            print("Hata:", e)
        time.sleep(CHECK_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    keep_alive()  # Web servisini ayakta tutar (Render pingler)
    main_loop()
