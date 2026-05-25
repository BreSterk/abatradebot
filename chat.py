import json
import anthropic
from database.db import get_connection
from config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

def get_recent_decisions(limit=10):
    conn = get_connection()
    cursor = conn.execute("""
        SELECT ticker, decision, conviction, thesis, wait_reason, 
               counter_argument, timestamp
        FROM decisions
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_recent_signals(limit=20):
    conn = get_connection()
    cursor = conn.execute("""
        SELECT ticker, source, catalyst_type, raw_score, raw_text, event_time
        FROM signals
        ORDER BY event_time DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def ask_claude(question: str, decisions: list, signals: list) -> str:
    context = f"""
Sen bir trading AI'sın. Kullanıcı seninle konuşuyor.

SON KARARLAR:
{json.dumps(decisions, indent=2, ensure_ascii=False)}

SON SİNYALLER:
{json.dumps(signals[:20], indent=2, ensure_ascii=False)}

Kullanıcının sorusunu yukarıdaki gerçek verilere dayanarak Türkçe olarak cevapla.
Eğer soru edilen hisse için veri yoksa bunu söyle.
Kısa ve net cevap ver.
"""
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        system=context,
        messages=[{"role": "user", "content": question}]
    )
    return response.content[0].text

def main():
    print("=" * 50)
    print("Trading AI — Sohbet Arayüzü")
    print("=" * 50)
    print("Botla konuşabilirsin. 'çık' yazarak çıkabilirsin.\n")

    while True:
        try:
            question = input("Sen: ").strip()
            if not question:
                continue
            if question.lower() in ["çık", "exit", "quit", "q"]:
                print("Görüşürüz!")
                break

            decisions = get_recent_decisions(10)
            signals = get_recent_signals(20)
            answer = ask_claude(question, decisions, signals)
            print(f"\nBot: {answer}\n")

        except KeyboardInterrupt:
            print("\nGörüşürüz!")
            break

if __name__ == "__main__":
    main()