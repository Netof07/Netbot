import os
import time
import requests
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from flask import Flask
from keepalive import start_keepalive_thread

# .env yükle
load_dotenv()

# Ayarlar
TG_TOKEN = os.getenv('TG_TOKEN')
TG_CHAT_ID = os.getenv('TG_CHAT_ID')
BASE_URL = os.getenv('BASE_URL', 'https://api.binance.com/api/v3')
VOLUME_MULTIPLIER = float(os.getenv('VOLUME_MULTIPLIER', '5'))  # 5x
REQUEST_SLEEP = float(os.getenv('REQUEST_SLEEP', '0.5'))       # Rate limit için
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

if not TG_TOKEN or not TG_CHAT_ID:
    raise SystemExit('TG_TOKEN ve TG_CHAT_ID .env dosyasında veya ortam değişkenlerinde olmalı!')

# Logging
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('netbot')

# Flask App (Render Web Service için)
app = Flask(__name__)

@app.route('/health')
def health():
    return 'Bot alive! 🚀', 200

# Telegram gönder
def telegram_send(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'HTML'},
            timeout=15
        )
        if resp.status_code != 200:
            logger.warning('Telegram hatası: %s %s', resp.status_code, resp.text)
        return resp.json()
    except Exception as e:
        logger.exception('Telegram gönderim hatası: %s', e)
        return None

# USDT çiftlerini al
def get_active_usdt_symbols():
    url = f"{BASE_URL}/exchangeInfo"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        symbols = [s['symbol'] for s in data.get('symbols', [])
                   if s.get('quoteAsset') == 'USDT' and s.get('status') == 'TRADING']
        logger.info(f"{len(symbols)} USDT çifti bulundu. Örnek: {symbols[:3]}")
        return symbols
    except Exception as e:
        logger.exception('exchangeInfo alınamadı: %s', e)
        return []

# Hacim kontrolü
def check_interval_for_symbol(symbol, interval):
    url = f"{BASE_URL}/klines?symbol={symbol}&interval={interval}&limit=2"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if len(data) < 2:
            logger.debug("%s %s: Yetersiz veri", symbol, interval)
            return None

        prev_vol = float(data[0][5])   # Önceki mum
        last_vol = float(data[1][5])   # Son mum
        prev_close = float(data[0][4])
        last_close = float(data[1][4])
        close_time_utc = datetime.fromtimestamp(int(data[1][6]) / 1000, tz=timezone.utc)
        tr_time = close_time_utc + timedelta(hours=3)

        if prev_vol <= 0:
            logger.debug("%s %s: Önceki hacim <=0, atlanıyor", symbol, interval)
            return None

        ratio = last_vol / prev_vol
        price_change = ((last_close - prev_close) / prev_close) * 100 if prev_close > 0 else 0

        # KDAUSDT için özel log
        if symbol == 'KDAUSDT':
            logger.info("KDAUSDT %s: %.2fx hacim, %+.2f%% fiyat (Kapanış: %s TR)",
                        interval, ratio, price_change, tr_time.strftime('%d %b %H:%M'))

        return {
            'symbol': symbol,
            'interval': interval,
            'ratio': ratio,
            'prev_vol': prev_vol,
            'last_vol': last_vol,
            'price_change': price_change,
            'tr_time': tr_time.strftime('%d %b %H:%M')
        }
    except Exception as e:
        logger.debug('Hata %s %s: %s', symbol, interval, e)
        return None
    finally:
        time.sleep(REQUEST_SLEEP)

# Tarama işi
def job():
    logger.info('Tarama başladı...')
    symbols = get_active_usdt_symbols()
    alerts = []
    debug_msgs = []

    for symbol in symbols:
        for interval in ('4h', '1d'):
            res = check_interval_for_symbol(symbol, interval)
            if res:
                if res['ratio'] >= VOLUME_MULTIPLIER:
                    alerts.append(res)
                elif res['ratio'] > 2:  # 2x+ için debug
                    debug_msgs.append(f"{symbol} {interval}: {res['ratio']:.2f}x")

    # Debug mesajı (2x+)
    if debug_msgs:
        telegram_send(f"<b>Debug (2x+):</b>\n" + "\n".join(debug_msgs[:10]))

    # Uyarı mesajı
    if alerts:
        msg = f"<b>{VOLUME_MULTIPLIER}x+ Hacim Artışı!</b>\n"
        for a in alerts:
            msg += f"• <code>{a['symbol']}</code> {a['interval']}: {a['ratio']:.1f}x (+{a['price_change']:.1f}% fiyat)\n"
        telegram_send(msg)
    else:
        telegram_send(f"<b>{'4h & 1d'}:</b> {VOLUME_MULTIPLIER}x+ artış yok.")

# Scheduler başlat
def start_scheduler():
    scheduler = BackgroundScheduler()
    # 4h: UTC 00:05, 04:05, 08:05, ... → TR 03:05, 07:05, ...
    scheduler.add_job(job, CronTrigger(minute=5, hour='0,4,8,12,16,20'), id='job_4h')
    # 1d: UTC 00:05 → TR 03:05
    scheduler.add_job(job, CronTrigger(minute=5, hour=0), id='job_1d')
    scheduler.start()
    logger.info('Scheduler cron ile başladı: 4h (her 4 saatte), 1d (her gün 03:05 TR)')

# Ana başlatma
if __name__ == '__main__':
    start_keepalive_thread()  # Render spin down'u önle
    telegram_send('Bot başlatıldı! Cron tarama aktif.')
    start_scheduler()

    # Flask ile web servisi (Render için zorunlu)
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
