import os
import time
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

# Flask uygulaması
app = Flask(__name__)

# Render için health endpoint
@app.route('/health')
def health():
    return 'Bot alive!', 200

# Ayarlar - Ortam değişkenlerinden al
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8411864218:AAG3cUnGDyw8UXa7GZkcEY6XXZHWHUmnXPo')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '795151448')
THRESHOLD = 500  # %500 artış (5 kat)
BINANCE_API_URL = 'https://api.binance.com'

def get_usdt_pairs():
    """USDT ile işlem gören çiftleri al."""
    try:
        response = requests.get(f'{BINANCE_API_URL}/api/v3/exchangeInfo')
        response.raise_for_status()
        exchange_info = response.json()
        usdt_pairs = [symbol['symbol'] for symbol in exchange_info['symbols'] if symbol['symbol'].endswith('USDT')]
        return usdt_pairs
    except Exception as e:
        print(f"USDT çiftleri alınamadı: {e}")
        return []

def get_volume_change(symbol, interval):
    """Mevcut ve önceki mumun hacmini al, % değişimi hesapla."""
    try:
        params = {'symbol': symbol, 'interval': interval, 'limit': 2}
        response = requests.get(f'{BINANCE_API_URL}/api/v3/klines', params=params)
        response.raise_for_status()
        klines = response.json()
        if len(klines) < 2:
            return None
        prev_volume = float(klines[0][5])  # Hacim 6. alanda (indeks 5)
        current_volume = float(klines[1][5])
        if prev_volume == 0:
            return None  # Sıfıra bölme hatasını önle
        change = ((current_volume - prev_volume) / prev_volume) * 100
        return change if change > 0 else None  # Sadece artışları döndür
    except Exception as e:
        print(f"Hata {symbol}: {e}")
        return None

def send_telegram_message(message):
    """Telegram botuna mesaj gönder."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Telegram mesajı gönderilemedi: {e}")

def check_volumes():
    """Hacimleri kontrol et ve 5 kat artışları bildir."""
    message = f"<b>Binance 5x Hacim Artışları (Saat: {time.strftime('%H:%M %d-%m-%Y')}):</b>\n"
    usdt_pairs = get_usdt_pairs()
    found = False

    for symbol in usdt_pairs:
        # 4 saatlik değişim
        change_4h = get_volume_change(symbol, '4h')
        if change_4h is not None and change_4h >= THRESHOLD:
            message += f"{symbol} 4s: {change_4h:.2f}% artış\n"
            found = True
        
        # 1 günlük değişim
        change_1d = get_volume_change(symbol, '1d')
        if change_1d is not None and change_1d >= THRESHOLD:
            message += f"{symbol} 1g: {change_1d:.2f}% artış\n"
            found = True
    
    if found:
        send_telegram_message(message)
    else:
        send_telegram_message("Bu saatte 5x hacim artışı yok.")

# Zamanlayıcı ayarı
scheduler = BackgroundScheduler()
scheduler.add_job(check_volumes, 'interval', hours=1)
scheduler.start()

# Flask uygulamasını başlat
if __name__ == '__main__':
    print("Bot başlatıldı. Render Web Service olarak çalışıyor.")
    port = int(os.environ.get('PORT', 5000))  # Render PORT ortam değişkenini kullan
    app.run(host='0.0.0.0', port=port)
