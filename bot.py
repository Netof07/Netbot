import os
import time
import requests
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv
from keepalive import start_keepalive_thread

load_dotenv()

TG_TOKEN = os.getenv('TG_TOKEN')
TG_CHAT_ID = os.getenv('TG_CHAT_ID')
BASE_URL = os.getenv('BASE_URL', 'https://api.binance.com/api/v3')
VOLUME_MULTIPLIER = float(os.getenv('VOLUME_MULTIPLIER', '5'))
REQUEST_SLEEP = float(os.getenv('REQUEST_SLEEP', '0.05'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

if not TG_TOKEN or not TG_CHAT_ID:
    raise SystemExit('❌ TG_TOKEN and TG_CHAT_ID must be set in environment variables or .env file.')

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('netbot')


def telegram_send(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={'chat_id': TG_CHAT_ID, 'text': text}, timeout=15)
        if resp.status_code != 200:
            logger.warning('Telegram send failed %s %s', resp.status_code, resp.text)
        return resp
    except Exception as e:
        logger.exception('Telegram send exception: %s', e)
        return None


def get_active_usdt_symbols():
    url = f"{BASE_URL}/exchangeInfo"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        symbols = [s['symbol'] for s in data.get('symbols', [])
                   if s.get('quoteAsset') == 'USDT' and s.get('status') == 'TRADING']
        return symbols
    except Exception as e:
        logger.exception('Failed to fetch exchangeInfo: %s', e)
        return []


def check_interval_for_symbol(symbol, interval, multiplier):
    url = f"{BASE_URL}/klines?symbol={symbol}&interval={interval}&limit=2"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if len(data) < 2:
            return None
        prev_vol = float(data[-2][5])
        last_vol = float(data[-1][5])
        ratio = (last_vol / prev_vol) if prev_vol > 0 else 1.0
        return {'symbol': symbol, 'interval': interval, 'ratio': ratio,
                'prev_vol': prev_vol, 'last_vol': last_vol}
    except Exception as e:
        logger.debug('Error fetching klines for %s %s: %s', symbol, interval, e)
        return None


def job():
    logger.info('⏱️ Job started: checking volumes...')
    symbols = get_active_usdt_symbols()
    alerts = []
    for symbol in symbols:
        for interval in ('4h', '1d'):
            res = check_interval_for_symbol(symbol, interval, VOLUME_MULTIPLIER)
            time.sleep(REQUEST_SLEEP)
            if not res:
                continue
            if res['ratio'] >= VOLUME_MULTIPLIER:
                alerts.append(res)
    if alerts:
        for a in alerts:
            msg = (f"⚡ {a['symbol']} hacmi {a['interval']} aralığında {a['ratio']:.2f}x arttı!\n"
                   f"Önceki: {a['prev_vol']:,.0f}, Şimdi: {a['last_vol']:,.0f}")
            telegram_send(msg)
    else:
        logger.info('No alerts found this run.')


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(job, IntervalTrigger(minutes=10), id='volume_job', replace_existing=True)
    scheduler.start()
    logger.info('Scheduler started: runs every 10 minutes.')


if __name__ == '__main__':
    start_keepalive_thread()
    telegram_send(f'✅ NetBot başlatıldı. Otomatik tarama aktif. (Her 10 dk, {VOLUME_MULTIPLIER}x)')
    start_scheduler()
    while True:
        time.sleep(10)
