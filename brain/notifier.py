import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8794369640:AAEmrkunWOD6gFP02azx5pQaXDtDiXSbDvU"
TELEGRAM_CHAT_ID = "6930274913"

def send_telegram(message: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        })
        if response.status_code == 200:
            logger.info("Telegram bildirimi gönderildi")
        else:
            logger.error(f"Telegram hatası: {response.text}")
    except Exception as e:
        logger.error(f"Telegram bağlantı hatası: {e}")

def notify_buy(ticker: str, conviction: float, thesis: str, entry_price: float):
    msg = f"""🟢 <b>BUY SİNYALİ</b>

📈 <b>{ticker}</b>
💰 Giriş Fiyatı: ${entry_price:.2f}
🎯 Conviction: {conviction:.0%}

📝 <b>Tez:</b>
{thesis[:300]}

⚡ Trading AI"""
    send_telegram(msg)

def notify_sell(ticker: str, pnl_pct: float, reason: str, entry_price: float, exit_price: float):
    emoji = "✅" if pnl_pct > 0 else "❌"
    reason_text = {
        "TP_HIT": "🎯 Take Profit",
        "SL_HIT": "🛑 Stop Loss",
        "TIME_EXIT": "⏰ Süre Doldu"
    }.get(reason, reason)
    
    msg = f"""{emoji} <b>POZİSYON KAPANDI</b>

📊 <b>{ticker}</b>
💵 Giriş: ${entry_price:.2f} → Çıkış: ${exit_price:.2f}
📈 PnL: <b>{pnl_pct:+.2f}%</b>
🔔 Sebep: {reason_text}

⚡ Trading AI"""
    send_telegram(msg)

def notify_wait(ticker: str, reason: str):
    msg = f"""⏳ <b>WAIT</b> — {ticker}

{reason[:200]}

⚡ Trading AI"""
    send_telegram(msg)