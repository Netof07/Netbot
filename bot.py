import os
import time
import requests
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from flask import Flask

# .env yükle
load_dotenv()

# Ayarlar
TG_TOKEN = os.getenv('TG_TOKEN')
TG_CHAT_ID = os.getenv('TG_CHAT_ID')
BASE_URL = os.getenv('BASE_URL', 'https://api.binance.com/api/v3')
VOLUME_MULTIPLIER = float(os.getenv('VOLUME_MULTIPLIER', '5'))  # 5x
REQUEST_SLEEP = float(os.getenv('REQUEST_SLEEP', '0.5'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

if not TG_TOKEN or not TG_CHAT_ID:
    logging.basicConfig(level='ERROR')
    logging.error('TG_TOKEN ve TG_CHAT_ID eksik!')
    raise SystemExit('TG_TOKEN ve TG_CHAT_ID gerekli!')

# Logging
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('netbot')

# Flask App
app = Flask(__name__)

@app.route('/health')
def health():
    return 'Bot alive! 05. dakikada tarama aktif', 200

# Telegram gönder
def telegram_send(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=15)
        if resp.status_code == 401:
            logger.error('Telegram 401: Token hatalı!')
        elif resp.status_code != 200:
            logger.warning('Telegram hatası: %s %s', resp.status_code, resp.text)
        return resp.json()
    except Exception as e:
        logger.exception('Telegram hatası: %s', e)
        return None

# USDT çiftlerini al
def get_active_usdt_symbols():
    url = f"{BASE_URL}/exchangeInfo"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        symbols = [s['symbol'] for s in r.json().get('symbols', [])
                   if s.get('quoteAsset') == 'USDT' and s.get('status') == 'TRADING']
        logger.info(f"{len(symbols)} USDT çifti bulundu.")
        return symbols
    except Exception as e:
        logger.exception('exchangeInfo hatası: %s', e)
        return []

# Hacim kontrolü
def check_interval_for_symbol(symbol, interval):
    url = f"{BASE_URL}/klines?symbol={symbol}&interval={interval}&limit=2"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if len(data) < 2:
            return None

        prev_vol = float(data[0][5])
        last_vol = float(data[1][5])
        prev_close = float(data[0][4])
        last_close = float(data[1][4])
        close_time_utc = datetime.fromtimestamp(int(data[1][6]) / 1000, tz=timezone.utc)
        tr_time = close_time_utc + timedelta(hours=3)

        if prev_vol <= 0:
            return None

        ratio = last_vol / prev_vol
        price_change = ((last_close - prev_close) / prev_close) * 100 if prev_close > 0 else 0

        # KDAUSDT için özel log
        if symbol == 'KDAUSDT':
            logger.info("KDAUSDT %s: %.2fx hacim, %+.2f%% fiyat (Kapanış: %s TR)",
                        interval, ratio, price_change, tr_time.strftime('%H:%M %d.%m'))

        return {
            'symbol': symbol,
            'interval': interval,
            'ratio': ratio,
            'prev_vol': prev_vol,
            'last_vol': last_vol,
            'price_change': price_change,
            'tr_time': tr_time.strftime('%H:%M %d.%m')
        }
    except Exception as e:
        logger.debug('Hata %s %s: %s', symbol, interval, e)
        return None
    finally:
        time.sleep(REQUEST_SLEEP)

# HER SAATİN 5. DAKİKASINDA TARAMA
def job():
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    logger.info(f"Tarama başladı: {tr_time.strftime('%H:%M %d.%m.%Y')} TR (her saat :05)")
    
    symbols = get_active_usdt_symbols()
    alerts = []
    debug_msgs = []

    for symbol in symbols:
        for interval in ('4h', '1d'):
            res = check_interval_for_symbol(symbol, interval)
            if res:
                if res['ratio'] >= VOLUME_MULTIPLIER:
                    alerts.append(res)
                elif res['ratio'] > 2:
                    debug_msgs.append(f"{symbol} {interval}: {res['ratio']:.2f}x")

    # Debug (2x+)
    if debug_msgs:
        telegram_send(f"<b>Debug (2x+):</b>\n" + "\n".join(debug_msgs[:10]))

    # Uyarı
    if alerts:
        msg = f"<b>{VOLUME_MULTIPLIER}x+ Hacim Artışı!</b>\n"
        for a in alerts:
            msg += f"• <code>{a['symbol']}</code> {a['interval']}: {a['ratio']:.1f}x (+{a['price_change']:.1f}%)\n"
        telegram_send(msg)
    else:
        telegram_send(f"<b>{tr_time.strftime('%H:%M')} TR:</b> 5x+ artış yok.")

# Scheduler
def start_scheduler():
    scheduler = BackgroundScheduler()
    # HER SAATİN 5. DAKİKASI (00:05, 01:05, 02:05, ...)
    scheduler.add_job(job, CronTrigger(minute=5), id='scan_05')
    scheduler.start()
    logger.info('Scheduler başladı: Her saat :05 TR\'de tarama aktif.')

# Ana
if __name__ == '__main__':
    telegram_send('Bot başlatıldı! Her saat :05 TR\'de 4h & 1d tarama aktif.')
    start_scheduler()

    # Render için Flask
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
