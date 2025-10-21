import os
import time
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

@app.route('/health')
def health():
    return 'Bot alive!', 200

# Ayarlar
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8411864218:AAG3cUnGDyw8UXa7GZkcEY6XXZHWHUmnXPo')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '795151448')
THRESHOLD = 500  # %500 artış
MIN_VOLUME_USDT = 10000  # Min hacim filtresi
BINANCE_API_URL = 'https://api.binance.com'

session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

def get_usdt_pairs():
    try:
        response = session.get(f'{BINANCE_API_URL}/api/v3/exchangeInfo', timeout=15)
        response.raise_for_status()
        exchange_info = response.json()
        usdt_pairs = [s['symbol'] for s in exchange_info['symbols'] if s['symbol'].endswith('USDT') and s['status'] == 'TRADING']
        print(f"Toplam {len(usdt_pairs)} USDT çifti bulundu. İlk 5: {usdt_pairs[:5]}...")
        print(f"BIOUSDT mevcut: {'BIOUSDT' in usdt_pairs}")
        print(f"FLOKIUSDT mevcut: {'FLOKIUSDT' in usdt_pairs}")
        return usdt_pairs
    except Exception as e:
        print(f"USDT çiftleri alınamadı: {e}")
        return []

def get_volume_change(symbol, interval):
    try:
        params = {'symbol': symbol, 'interval': interval, 'limit': 2}
        response = session.get(f'{BINANCE_API_URL}/api/v3/klines', params=params, timeout=15)
        response.raise_for_status()
        klines = response.json()
        if len(klines) < 2:
            print(f"{symbol} ({interval}): Yetersiz mum verisi.")
            return None
        prev_volume = float(klines[0][5])
        current_volume = float(klines[1][5])
        current_close_time = int(klines[1][6]) / 1000
        # UTC timestamp'i TR saati (+3 saat) yap
        utc_time = datetime.fromtimestamp(current_close_time, tz=timezone.utc)
        tr_time = utc_time + timedelta(hours=3)
        now_utc = datetime.now(timezone.utc)
        now_tr = now_utc + timedelta(hours=3)
        # Mum kapanışının yeni olup olmadığını kontrol et (son 10 dk)
        if (now_tr - tr_time).total_seconds() > 600:
            print(f"{symbol} ({interval}): Mum eski ({tr_time}), atlanıyor.")
            return None
        if prev_volume == 0:
            print(f"{symbol} ({interval}): Önceki hacim sıfır.")
            return None
        # Min hacim kontrolü (önceki mum hacmi * kapanış fiyatı)
        prev_close_price = float(klines[0][4])
        if prev_volume * prev_close_price < MIN_VOLUME_USDT:
            print(f"{symbol} ({interval}): Düşük hacim ({prev_volume * prev_close_price:.2f} USDT).")
            return None
        change = ((current_volume - prev_volume) / prev_volume) * 100
        print(f"{symbol} ({interval}): {change:.2f}% artış, Kapanış={tr_time}")
        return change if change > 0 else None
    except Exception as e:
        print(f"Hata {symbol} ({interval}): {e}")
        return None
    finally:
        time.sleep(0.5)

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = session.get(url, params=params, timeout=15)
        response.raise_for_status()
        print(f"Telegram mesajı gönderildi: {message[:50]}...")
        return response.json()
    except Exception as e:
        print(f"Telegram mesajı gönderilemedi: {e}")

def check_volumes_4h():
    tr_time = time.strftime('%H:%M %d-%m-%Y', time.localtime(time.time() + 3*3600))
    print(f"4h tarama başlıyor (TR): {tr_time}")
    message = f"<b>Binance 5x Hacim Artışları (4h, TR Saat: {tr_time}):</b>\n"
    usdt_pairs = get_usdt_pairs()
    found = False
    debug_log = []

    for symbol in usdt_pairs:
        change_4h = get_volume_change(symbol, '4h')
        if change_4h is None:
            debug_log.append(f"{symbol}: Veri yok veya sıfır hacim")
        elif change_4h >= THRESHOLD:
            message += f"{symbol} 4s: {change_4h:.2f}% artış\n"
            found = True
            debug_log.append(f"{symbol}: {change_4h:.2f}% (YAKALANDI)")
        else:
            debug_log.append(f"{symbol}: {change_4h:.2f}% (eşik altında)")
        if symbol in ['BIOUSDT', 'FLOKIUSDT']:
            print(f"Özel log: {symbol} 4h: {change_4h}%")

    if found:
        send_telegram_message(message)
    else:
        send_telegram_message("Bu saatte 4h için 5x hacim artışı yok.")
    # Debug log'u kısaltarak gönder (tüm sembolleri değil, örnekleri)
    if debug_log:
        sample_log = debug_log[:10]  # İlk 10'u al
        send_telegram_message(f"<b>4h Debug Log (örnek):</b>\n" + "\n".join(sample_log) + f"\nToplam taranan: {len(usdt_pairs)}")

def check_volumes_1d():
    tr_time = time.strftime('%H:%M %d-%m-%Y', time.localtime(time.time() + 3*3600))
    print(f"1d tarama başlıyor (TR): {tr_time}")
    message = f"<b>Binance 5x Hacim Artışları (1d, TR Saat: {tr_time}):</b>\n"
    usdt_pairs = get_usdt_pairs()
    found = False
    debug_log = []

    for symbol in usdt_pairs:
        change_1d = get_volume_change(symbol, '1d')
        if change_1d is None:
            debug_log.append(f"{symbol}: Veri yok veya sıfır hacim")
        elif change_1d >= THRESHOLD:
            message += f"{symbol} 1g: {change_1d:.2f}% artış\n"
            found = True
            debug_log.append(f"{symbol}: {change_1d:.2f}% (YAKALANDI)")
        else:
            debug_log.append(f"{symbol}: {change_1d:.2f}% (eşik altında)")
        if symbol in ['BIOUSDT', 'FLOKIUSDT']:
            print(f"Özel log: {symbol} 1d: {change_1d}%")

    if found:
        send_telegram_message(message)
    else:
        send_telegram_message("Bu saatte 1d için 5x hacim artışı yok.")
    # Debug log'u kısaltarak gönder
    if debug_log:
        sample_log = debug_log[:10]  # İlk 10'u al
        send_telegram_message(f"<b>1d Debug Log (örnek):</b>\n" + "\n".join(sample_log) + f"\nToplam taranan: {len(usdt_pairs)}")

scheduler = BackgroundScheduler()
scheduler.add_job(check_volumes_4h, 'cron', minute=5, hour='*/4')
scheduler.add_job(check_volumes_1d, 'cron', minute=5, hour=0)
scheduler.start()

if __name__ == '__main__':
    print("Bot başlatıldı. Render Web Service olarak çalışıyor.")
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
