NetBot - Volume scanner (4h & 1d, hourly @ :05)

Setup:
1. Copy .env.example -> .env and set TG_TOKEN and TG_CHAT_ID (do not push .env to public repo).
2. Install packages: pip install -r requirements.txt
3. Run: python bot.py

Deploy notes (Render or other PaaS):
- Make a Web Service and set start command: python bot.py
- Set environment variables in service dashboard (TG_TOKEN, TG_CHAT_ID...)
- Use UptimeRobot to ping the service URL to keep the container alive if needed.
