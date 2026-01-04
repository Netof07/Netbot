import os
import time
import requests
import logging
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

def get_active_usdt_symbols():
    try:
        r = requests.get(f"{BASE_URL}/exchangeInfo", timeout=10)
        r.raise_for_status()
        symbols = [s['symbol'] for s in r.json().get('symbols', [])
                   if s.get('quoteAsset') == 'USDT' and s.get('status') == 'TRADING']
        symbols.sort()
        logger.info(f"{len(symbols)} USDT çifti bulundu.")
        return symbols
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

def job_4h():
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    logger.info(f"4h TARAMA BAŞLADI: {tr_time.strftime('%H:%M %d.%m.%Y')} TR")
    telegram_send(f"<b>4h TARAMA:</b> {tr_time.strftime('%H:%M')} TR")
    symbols = get_active_usdt_symbols()
    alerts = []
    debug_msgs = []
    for symbol in symbols:
        res = check_current_vs_previous_mum(symbol, '4h')
        if res:
            if res['ratio'] >= VOLUME_MULTIPLIER:
                alerts.append(res)
            elif res['ratio'] > 1.5:
                debug_msgs.append(f"{symbol} 4h: {res['ratio']:.2f}x")
    if debug_msgs:
        telegram_send(f"<b>1.5x+ (4h):</b>\n" + "\n".join(debug_msgs[:10]))
    if alerts:
        msg = f"<b>{VOLUME_MULTIPLIER}x+ BULUNDU (4h)!</b>\n"
        for a in alerts:
            msg += f"• <code>{a['symbol']}</code> 4h: {a['ratio']:.1f}x\n"
        telegram_send(msg)
    else:
        telegram_send(f"<b>{tr_time.strftime('%H:%M')} (4h):</b> 5x+ yok.")

def job_1d():
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    logger.info(f"1d TARAMA BAŞLADI: {tr_time.strftime('%H:%M %d.%m.%Y')} TR")
    telegram_send(f"<b>1d TARAMA:</b> {tr_time.strftime('%H:%M')} TR")
    symbols = get_active_usdt_symbols()
    alerts = []
    for symbol in symbols:
        res = check_current_vs_previous_mum(symbol, '1d')
        if res and res['ratio'] >= VOLUME_MULTIPLIER:
            alerts.append(res)
    if alerts:
        msg = f"<b>{VOLUME_MULTIPLIER}x+ BULUNDU (1d)!</b>\n"
        for a in alerts:
            msg += f"• <code>{a['symbol']}</code> 1d: {a['ratio']:.1f}x\n"
        telegram_send(msg)
    else:
        telegram_send(f"<b>{tr_time.strftime('%H:%M')} (1d):</b> 5x+ yok.")

# Scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(job_4h, CronTrigger(minute=5, hour='*/4'))  # 4h: TR 03:05, 07:05, 11:05, 15:05, 19:05, 23:05
scheduler.add_job(job_1d, CronTrigger(minute=5, hour=0))      # 1d: TR 03:05
scheduler.start()
logger.info('Scheduler başladı: 4h -> */4:05, 1d -> 00:05 UTC')

if __name__ == '__main__':
    telegram_send('Bot yerel olarak başladı.')
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
else:
    telegram_send('Bot Render’da başladı! Tarama 4h ve 1d mum kapanışlarında.')
