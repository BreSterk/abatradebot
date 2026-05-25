import requests
import json
import time
import logging
from anthropic import Anthropic
from database.db import get_connection
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8794369640:AAEmrkunWOD6gFP02azx5pQaXDtDiXSbDvU"
TELEGRAM_CHAT_ID = "6930274913"
client = Anthropic(api_key=settings.anthropic_api_key)

def send_message(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    })

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    response = requests.get(url, params=params)
    return response.json()

def get_recent_decisions(limit=10):
    conn = get_connection()
    cursor = conn.execute("""
        SELECT ticker, decision, conviction, thesis, wait_reason, timestamp
        FROM decisions ORDER BY timestamp DESC LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_open_positions():
    conn = get_connection()
    cursor = conn.execute("""
        SELECT ticker, entry_price, current_price, opened_at, size_pct
        FROM positions WHERE status = 'open'
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_trade_results():
    conn = get_connection()
    cursor = conn.execute("""
        SELECT * FROM trade_results ORDER BY timestamp DESC LIMIT 10
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def ask_claude(question: str) -> str:
    decisions = get_recent_decisions(10)
    positions = get_open_positions()
    results = get_trade_results()

    context = f"""Sen bir trading AI'sın. Kullanıcı seninle Telegram üzerinden konuşuyor.

SON KARARLAR:
{json.dumps(decisions, indent=2, ensure_ascii=False)}

AÇIK POZİSYONLAR:
{json.dumps(positions, indent=2, ensure_ascii=False)}

SON TRADE SONUÇLARI:
{json.dumps(results, indent=2, ensure_ascii=False)}

Türkçe, kısa ve net cevap ver. Telegram formatında yaz."""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        system=context,
        messages=[{"role": "user", "content": question}]
    )
    return response.content[0].text

def main():
    logger.info("Telegram bot başlatıldı...")
    send_message("🤖 Trading AI aktif! Sorularını yazabilirsin.")
    
    offset = None
    while True:
        try:
            updates = get_updates(offset)
            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                
                if "message" not in update:
                    continue
                
                msg = update["message"]
                chat_id = msg["chat"]["id"]
                text = msg.get("text", "")
                
                if not text:
                    continue
                
                logger.info(f"Mesaj alındı: {text}")
                
                # Cevap üret
                response = ask_claude(text)
                
                # Gönder
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": response,
                        "parse_mode": "HTML"
                    }
                )
                
        except Exception as e:
            logger.error(f"Hata: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()