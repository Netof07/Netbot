# NetBot - Binance Volume Alert Bot (final)

Bu paket Render üzerinde ücretsiz Web Service (Flask healthcheck) olarak çalışacak şekilde hazırlanmıştır.
- 4 saatlik (4h) ve 1 günlük (1d) mum hacimlerini kontrol eder.
- Eğer son mum hacmi önceki muma göre 5x veya daha fazla artmışsa Telegram'a bildirim gönderir.
- Bildirimler tekrar etmeyi önlemek için aynı candle için bir kere gönderilir.
- Render ücretsiz Web Service ile uyumlu olması için küçük bir Flask healthcheck endpoint'i içerir.

**Dosyalar**
- net.py           -> Ana uygulama
- requirements.txt -> Gerekli Python paketleri
- Procfile         -> Render start komutu (web: python net.py)
- .env.example     -> Ortam değişkenleri örneği

**Kurulum (yerel / GitHub)**
1. Bu dizini GitHub repoya yükle (dosyaları zip yerine direkt yerleştirin).
2. Render'da yeni Web Service yaratın ve repo'yu bağlayın.
3. Render ayarlarında:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python net.py`
   - Port: 10000 (veya Varsayılan)
   - Environment variables (Render panel):
     - TG_TOKEN : <bot token>
     - TG_CHAT_ID : <your chat id>
     - (opsiyonel) ALERT_MULTIPLIER, CHECK_INTERVAL_MINUTES, BASE_URL
4. Deploy edin ve Logs'tan "NetBot başlatıldı" veya Telegram mesajını kontrol edin.

**Notlar**
- Repo içinde zip dosyası (ör. netbot_render.zip) bulunmamalıdır. Render zip dosyalarını klasör gibi algılamaya çalışır ve hata verir.
- Eğer ilk defa çalıştırmada çok sayıda uyarı gelirse, bu genellikle ilk run'ın geçmiş mumları kontrol etmesinden dolayı olur. Kod, aynı candle için sadece bir kere uyarı gönderir.
- Uptime Robot ile `/` endpoint'ine periyodik ping atarsanız, Render servisinizin daha az uyuyup daha stabil çalışmasını sağlayabilirsiniz.
