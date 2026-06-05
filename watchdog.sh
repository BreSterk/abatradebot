#!/bin/bash
TOKEN="8794369640:AAEmrkunWOD6gFP02azx5pQaXDtDiXSbDvU"
CHAT="6930274913"

alert() {
    curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
        -d "chat_id=${CHAT}" \
        -d "text=ABA UYARI: $1" > /dev/null
}

if ! pgrep -f "main.py" > /dev/null; then
    alert "main.py durdu, yeniden baslatiliyor"
    cd /root/trading_ai && nohup uv run python main.py >> /root/trading_ai/logs/main.log 2>&1 &
fi

if ! pgrep -f "telegram_chat.py" > /dev/null; then
    alert "telegram_chat.py durdu, yeniden baslatiliyor"
    cd /root/trading_ai && nohup uv run python telegram_chat.py >> /root/trading_ai/logs/telegram.log 2>&1 &
fi

LAST=$(stat -c %Y /root/trading_ai/logs/main.log 2>/dev/null || echo 0)
NOW=$(date +%s)
if [ $((NOW - LAST)) -gt 1800 ]; then
    alert "Log 30 dakikadir guncellenmedi, sistem donmus olabilir"
fi
