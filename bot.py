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
REQUEST_SLEEP = float(os.getenv('REQUEST_SLEEP', '0.1'))       # Hızlı tarama
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
    return 'Bot alive! Güncel mum spike + 200 pair', 200

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

# USDT çiftlerini al → Sadece yüksek hacimli 200 (alfabetik)
def get_active_usdt_symbols():
    url = f"{BASE_URL}/exchangeInfo"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        symbols = [s['symbol'] for s in r.json().get('symbols', [])
                   if s.get('quoteAsset') == 'USDT' and s.get('status') == 'TRADING']
        symbols.sort()  # Alfabetik sıralama
        high_volume = symbols[:200]  # İlk 200 (en aktifler)
        logger.info(f"{len(high_volume)} USDT çifti taranıyor (yüksek hacimli ilk 200).")
        return high_volume
    except Exception as e:
        logger.exception('exchangeInfo hatası: %s', e)
        return []

# GÜNCEL MUM vs. BİR ÖNCEKİ KAPANAN MUM (5x+ yakala)
def check_current_vs_previous_mum(symbol, interval):
    url = f"{BASE_URL}/klines?symbol={symbol}&interval={interval}&limit=2"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        if len(data) < 2:
            return None

        # Bir önceki KAPANAN mum
        prev_vol = float(data[0][5])
        prev_close_time = datetime.fromtimestamp(int(data[0][6]) / 1000, tz=timezone.utc)
        prev_tr_time = prev_close_time + timedelta(hours=3)

        # Şu anki (KAPANMAMIŞ) mum
        current_vol = float(data[1][5])
        current_close_time = datetime.fromtimestamp(int(data[1][6]) / 1000, tz=timezone.utc)
        current_tr_time = current_close_time + timedelta(hours=3)

        if prev_vol <= 0:
            return None

        ratio = current_vol / prev_vol

        return {
            'symbol': symbol,
            'interval': interval,
            'ratio': ratio,
            'prev_vol': prev_vol,
            'current_vol': current_vol,
            'prev_tr_time': prev_tr_time.strftime('%H:%M %d.%m'),
            'current_tr_time': current_tr_time.strftime('%H:%M %d.%m')
        }
    except Exception as e:
        logger.debug('Hata %s %s: %s', symbol, interval, e)
        return None
    finally:
        time.sleep(REQUEST_SLEEP)

# TARAMA (Her saat :05 → Güncel mum spike)
def job():
    tr_time = datetime.now(timezone.utc) + timedelta(hours=3)
    logger.info(f"Tarama başladı: {tr_time.strftime('%H:%M %d.%m.%Y')} TR")

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
                    debug_msgs.append(f"{symbol} {interval}: {res['ratio']:.2f}x (güncel)")

    # Debug (1.5x+ güncel mum)
    if debug_msgs:
        telegram_send(f"<b>Debug (1.5x+ güncel):</b>\n" + "\n".join(debug_msgs[:15]))

    # Uyarı (5x+ güncel mum)
    if alerts:
        msg = f"<b>{VOLUME_MULTIPLIER}x+ GÜNCEL MUM ARTIŞI!</b>\n"
        for a in alerts:
            msg += (f"• <code>{a['symbol']}</code> {a['interval']}: {a['ratio']:.1f}x\n"
                    f"  Önceki: {a['prev_vol']:,.0f} | Güncel: {a['current_vol']:,.0f}\n"
                    f"  Kapanış: {a['current_tr_time']} TR\n")
        telegram_send(msg)
    else:
        telegram_send(f"<b>{tr_time.strftime('%H:%M')} TR:</b> 5x+ güncel artış yok.")

# Scheduler (Her saat :05)
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(job, CronTrigger(minute=5), id='scan_05')
    scheduler.start()
    logger.info('Scheduler başladı: Her saat :05 TR\'de güncel mum tarama aktif.')

# Ana
if __name__ == '__main__':
    telegram_send('Bot aktif! 200 yüksek hacimli çift + güncel mum spike.')
    start_scheduler()

    # Render için Flask
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
