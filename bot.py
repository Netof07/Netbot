import os
import time
import requests
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from keepalive import start_keepalive_thread

# Load environment variables (from .env file when present)
load_dotenv()

# Environment variables
TG_TOKEN = os.getenv('TG_TOKEN')
TG_CHAT_ID = os.getenv('TG_CHAT_ID')
BASE_URL = os.getenv('BASE_URL', 'https://api.binance.com/api/v3')
VOLUME_MULTIPLIER = float(os.getenv('VOLUME_MULTIPLIER', '5'))
REQUEST_SLEEP = float(os.getenv('REQUEST_SLEEP', '0.05'))  # seconds between requests
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

# Check required vars
if not TG_TOKEN or not TG_CHAT_ID:
    raise SystemExit('❌ TG_TOKEN and TG_CHAT_ID must be set in .env file or environment.')

# Logging config
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('netbot')

# Telegram message sender
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

# Fetch active USDT trading pairs
def get_active_usdt_symbols():
    url = f"{BASE_URL}/exchangeInfo"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        symbols = [s['symbol'] for s in data.get('symbols', [])
                   if s.get('quoteAsset') == 'USDT' and s.get('status') == 'TRADING']
        logger.info('Fetched %d USDT symbols', len(symbols))
        return symbols
    except Exception as e:
        logger.exception('Failed to fetch exchangeInfo: %s', e)
        return []

# Check 4h & 1d volumes for symbol
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
        ratio = (last_vol / prev_vol) if prev_vol > 0 else (float('inf') if last_vol > 0 else 1.0)
        return {
            'symbol': symbol,
            'interval': interval,
            'prev_vol': prev_vol,
            'last_vol': last_vol,
            'ratio': ratio
        }
    except Exception as e:
        logger.debug('Error fetching klines for %s %s: %s', symbol, interval, e)
        return None

# Main scan job
def job():
    logger.info('Job started: checking volumes for 4h and 1d intervals (x%.2f)', VOLUME_MULTIPLIER)
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
        logger.info('Found %d alerts', len(alerts))
        for a in alerts:
            msg = (
                f"⚡ {a['symbol']} hacmi {a['interval']} aralığında {a['ratio']:.2f}x arttı!\n"
                f"Önceki: {a['prev_vol']:,.0f}, Şimdi: {a['last_vol']:,.0f}"
            )
            telegram_send(msg)
    else:
        logger.info('No alerts found this run.')

# Scheduler setup
def start_scheduler():
    scheduler = BackgroundScheduler()
    trigger = CronTrigger(minute='5')  # every hour at minute 5
    scheduler.add_job(job, trigger, id='volume_job', replace_existing=True)
    scheduler.start()
    logger.info('Scheduler started: runs every hour at minute 5')

# App entrypoint
if __name__ == '__main__':
    # Keepalive for Render / UptimeRobot
    start_keepalive_thread()
    telegram_send(f'✅ NetBot başlatıldı. Otomatik tarama aktif. (4h & 1d, {VOLUME_MULTIPLIER}x)')
    start_scheduler()
    try:
        while True:
            time.sleep(10)
    except (KeyboardInterrupt, SystemExit):
        logger.info('Shutting down...') 
