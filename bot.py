import os
import time
import requests
import logging
import threading
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from flask import Flask

load_dotenv()

# Ortam değişkenleri
TG_TOKEN = os.getenv('TG_TOKEN')
TG_CHAT_ID = os.getenv('TG_CHAT_ID')
BASE_URL = os.getenv('BASE_URL', 'https://api.binance.com/api/v3')
VOLUME_MULTIPLIER = float(os.getenv('VOLUME_MULTIPLIER', '5'))
REQUEST_SLEEP = float(os.getenv('REQUEST_SLEEP', '0.1'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
SERVICE_URL = os.getenv('SERVICE_URL', 'https://netbot-w3r8.onrender.com/health')

if not TG_TOKEN or not TG_CHAT_ID:
    raise SystemExit('TG_TOKEN ve TG_CHAT_ID gerekli!')

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('netbot')

app = Flask(__name__)

@app.route('/health')
def health():
    return 'Bot alive! gunicorn + scheduler aktif', 200

def telegram_send(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={'chat_id': TG_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=15)
        if resp.status_code != 200:
            logger.warning('Telegram hatası: %s %s', resp.status_code, resp.text)
    except Exception as e:
        logger.exception('Telegram hatası: %s', e)

def self_ping():
    while True:
        try:
            requests.get(SERVICE_URL, timeout=10)
            logger.debug('Self-ping OK')
        except:
            pass
        time.sleep(840)

def get_active_usdt_symbols():
    try:
        r = requests.get(f"{BASE_URL}/exchangeInfo", timeout=10)
        r.raise_for_status()
        symbols = [s['symbol'] for s in r.json().get('symbols', [])
                   if s.get('quoteAsset') == 'USDT' and s.get('status') == 'TRADING']
        symbols.sort()
        high_volume = symbols[:300]  # VELOUSDT garanti
        logger.info(f"{len(high_volume)} çift taranıyor.")
        return high_volume
    except Exception as e:
        logger.exception('exchangeInfo hatası: %s', e)
        return []

def check_current_vs_previous_mum(symbol, interval):
    try:
        r = requests.get(f"{BASE_URL}/klines?symbol={symbol}&interval={interval}&limit=2", timeout=10)
        r.raise_for_status()
        data = r.json()
        if len(data) < 2:
            return None

        prev_vol = float(data[0][5])
        current_vol = float(data[1][5])
        if prev_vol <= 0:
            return None

        ratio = current_vol / prev_vol
        return {
            'symbol': symbol, 'interval': interval, 'ratio': ratio,
            'prev_vol': prev_vol, 'current_vol': current_vol
        }
    except Exception as e:
        logger.debug('Hata %s %s: %s', symbol, interval, e)
        return None
    finally:
        time.sleep(REQUEST_SLEEP)

def job():
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    logger.info(f"TARAMA BAŞLADI: {tr_time.strftime('%H:%M %d.%m.%Y')} TR")
    telegram_send(f"<b>TARAMA:</b> {tr_time.strftime('%H:%M')} TR")

    symbols = get_active_usdt_symbols()
    alerts = []
    debug_msgs = []

    for symbol in symbols:
        for interval in ('4h', '1d'):
            res = check_current_vs_previous_mum(symbol, interval)
            if res:
                if res['ratio'] >= VOLUME_MULTIPLIER:
                    alerts.append(res)
                elif res['ratio'] > 1.5:
                    debug_msgs.append(f"{symbol} {interval}: {res['ratio']:.2f}x")

    if debug_msgs:
        telegram_send(f"<b>1.5x+:</b>\n" + "\n".join(debug_msgs[:10]))

    if alerts:
        msg = f"<b>{VOLUME_MULTIPLIER}x+ BULUNDU!</b>\n"
        for a in alerts:
            msg += f"• <code>{a['symbol']}</code> {a['interval']}: {a['ratio']:.1f}x\n"
        telegram_send(msg)
    else:
        telegram_send(f"<b>{tr_time.strftime('%H:%M')}:</b> 5x+ yok.")

# SCHEDULER HER ZAMAN ÇALIŞIR
scheduler = BackgroundScheduler()
scheduler.add_job(job, CronTrigger(minute=5), id='scan_05')
scheduler.start()
logger.info('Scheduler gunicorn ile başlatıldı!')

# SELF-PING THREAD
ping_thread = threading.Thread(target=self_ping, daemon=True)
ping_thread.start()
logger.info('Self-ping thread başladı.')

# FLASK UYGULAMASI
if __name__ == '__main__':
    # SADECE LOCAL TEST İÇİN
    telegram_send('Bot yerel olarak başladı.')
    app.run(host='0.0.0.0', port=5000, debug=True)
else:
    # GUNICORN İLE ÇALIŞIRKEN
    telegram_send('Bot gunicorn ile başladı! Tarama her :05\'te.')
