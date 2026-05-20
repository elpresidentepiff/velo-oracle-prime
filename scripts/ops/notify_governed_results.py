import os
import requests
import json
from dotenv import load_dotenv

def send_to_telegram():
    load_dotenv('velo-oracle-prime/.env')
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    
    if not token or not chat_id:
        print("X FAIL: Telegram credentials missing.")
        return

    message = """🛡️ *VÉLØ GOVERNED EXECUTION REPORT*
📅 Date: 20 Apr 2026 (Tomorrow)

*Runtime Truth: Router v1 Sitting in Throat.*

📊 *Card Summary:*
- Total Scored: 52
- **FORTRESS (Win):** 6
- **FRAME (EW/Place):** 20
- **PASS (Amputated):** 10
- **VISION (Note):** 16

🔥 *Fortress Authorization:*
- Ayr 4:15 | West Hill Verde
- Bangor-on-Dee 2:27 | Park Princess
- Nottingham 4:37 | Hen Party
- Thirsk 1:37 | Bai Tong
- Thirsk 2:12 | Advance T
- Bellewstown 5:35 | Gill

✅ *Institutional Status:*
Execution Chain: MAPPED
Amputation Gate: ACTIVE
Strike Lift (Est): +11.9%

*Governed by AEGIS Product Router v1*"""

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    resp = requests.post(url, json=payload)
    if resp.ok:
        print("✓ SUCCESS: Governed Results for April 20th sent to Telegram.")
    else:
        print(f"X FAIL: Telegram API error: {resp.text}")

if __name__ == "__main__":
    send_to_telegram()
