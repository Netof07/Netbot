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
            print(f"{symbol} ({interval}): Yetersiz mum
