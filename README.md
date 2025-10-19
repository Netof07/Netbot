# Binance 5x Hacim Artışı Botu

Bu bot, Binance’te USDT işlem çiftlerinde 4 saatlik ve 1 günlük K-linelerde önceki muma göre 5 kat (%500) veya daha fazla hacim artışı olanları her saat tarar ve Telegram’a bildirir. Render’da ücretsiz Web Service olarak çalışır. Binance REST API’sini kullanır, API anahtarı gerekmez.

## Kurulum (Yerel Test)
1. **Gerekli kütüphaneleri yükle**:
   ```bash
   pip install -r requirements.txt
