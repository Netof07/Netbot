import os
import time
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Flask uygulaması
app = Flask(__name__)

# Render için health endpoint
@app.route('/health')
def health():
    return 'Bot alive!', 200

# Ayarlar
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8411864218:AAG3cUnGDyw8UXa7GZkcEY6XXZHWHUmnXPo')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '795151448')
THRESHOLD = 500  # %500 artış
BINANCE_API_URL = 'https://api.binance.com'

# Requests için retry ayarı
session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

def get_usdt_pairs():
    """USDT ile işlem gören çiftleri al."""
    try:
        response = session.get(f'{BINANCE_API_URL}/api/v3/exchangeInfo', timeout=15)
        response.raise_for_status()
        exchange_info = response.json()
        usdt_pairs = [symbol['symbol'] for symbol in exchange_info['symbols'] if symbol['symbol'].endswith('USDT')]
        print(f"Toplam {len(usdt_pairs)} USDT çifti bulundu. İlk 5: {usdt_pairs[:5]}...")
        return usdt_pairs
    except Exception as e:
        print(f"USDT çiftleri alınamadı: {e}")
        return ['LAUSDT', 'CHRUSDT']  # Varsayılan sorunlu çiftler

def get_volume_change(symbol, interval):
    """Mevcut ve önceki mumun hacmini al, % değişimi hesapla."""
    try:
        params = {'symbol': symbol, 'interval': interval, 'limit': 2}
        response = session.get(f'{BINANCE_API_URL}/api/v3/klines', params=params, timeout=15)
        response.raise_for_status()
        klines = response.json()
        if len(klines) < 2:
            print(f"{symbol} ({interval}): Yetersiz mum verisi (sadece {len(klines)} mum).")
            return None
        prev_volume = float(klines[0][5])  # Önceki mum hacmi (indeks 5)
        current_volume = float(klines[1][5])  # Mevcut mum hacmi (indeks 5)
        prev_close_time = int(klines[0][6]) / 1000  # Önceki mum kapanış (saniye)
        current_close_time = int(klines[1][6]) / 1000  # Mevcut mum kapanış
        if prev_volume == 0:
            print(f"{symbol} ({interval}): Önceki hacim sıfır ({prev_volume}), hesaplama yapılamadı.")
            return None
        change = ((current_volume - prev_volume) / prev_volume) * 100
        tr_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(current_close_time + 3*3600))  # TR +3 saat
        print(f"{symbol} ({interval}): Önceki hacim={prev_volume:.2f}, Mevcut hacim={current_volume:.2f}, "
              f"Değişim={change:.2f}%, TR kapanış={tr_time}")
        return change if change > 0 else None
    except Exception as e:
        print(f"Hata {symbol} ({interval}): {e}")
        return None

def send_telegram_message(message):
    """Telegram botuna mesaj gönder."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = session.get(url, params=params, timeout=15)
        response.raise_for_status()
        print(f"Telegram mesajı gönderildi: {message[:50]}...")
        return response.json()
    except Exception as e:
        print(f"Telegram mesajı gönderilemedi: {e}")

def check_volumes():
    """Hacimleri kontrol et ve 5 kat artışları bildir."""
    tr_time = time.strftime('%H:%M %d-%m-%Y', time.localtime(time.time() + 3*3600))
    print(f"Tarama başlıyor (TR): {tr_time}")
    message = f"<b>Binance 5x Hacim Artışları (TR Saat: {tr_time}):</b>\n"
    usdt_pairs = get_usdt_pairs()
    found = False

    # Öncelikli çiftler: LAUSDT ve CHRUSDT
    priority_pairs = ['LAUSDT', 'CHRUSDT']
    for symbol in priority_pairs:
        if symbol in usdt_pairs:
            usdt_pairs.remove(symbol)
            usdt_pairs.insert(0, symbol)

    for symbol in usdt_pairs[:50]:  # İlk 50 çifti tara (rate limit için)
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

# Zamanlayıcı ayarı (4 saatlik mum kapanışlarından 5 dakika sonra, TR saatiyle)
scheduler = BackgroundScheduler()
scheduler.add_job(check_volumes, 'cron', minute=5, hour='*/4')  # UTC: 00:05, 04:05, 08:05; TR: 03:05, 07:05, 11:05
scheduler.start()

# Flask uygulamasını başlat
if __name__ == '__main__':
    print("Bot başlatıldı. Render Web Service olarak çalışıyor.")
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port) 
