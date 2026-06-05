import sys
sys.path.insert(0, '/root/trading_ai')
from brain.position_manager import PositionManager
import yfinance as yf

CAPITAL = 10000.0
pm = PositionManager()
positions = pm.get_open_positions()

print("\nACIK POZISYONLAR:")
print("---------------------------------------")
total_unrealized = 0.0
for p in positions:
    try:
        hist = yf.Ticker(p['ticker']).history(period='1d')
        current = float(hist['Close'].iloc[-1]) if not hist.empty else p['current_price']
    except:
        current = p['current_price']
    pnl_pct = ((current - p['entry_price']) / p['entry_price']) * 100
    size_pct = p['size_pct'] * 100 if p['size_pct'] < 1.0 else p['size_pct']
    pnl_dollar = CAPITAL * (size_pct / 100) * (pnl_pct / 100)
    total_unrealized += pnl_dollar
    print(f"  {p['ticker']:<6} {p['entry_price']:>7.2f} -> {current:>7.2f}  {pnl_pct:+.2f}%  ({pnl_dollar:+.0f}$)")

print("---------------------------------------")

from database.db import get_connection
conn = get_connection()
trade_rows = conn.execute("SELECT tr.pnl_pct, p.size_pct FROM trade_results tr JOIN positions p ON tr.position_id = p.id").fetchall()
rows = conn.execute("SELECT p.ticker, tr.pnl_pct, tr.exit_reason FROM trade_results tr JOIN positions p ON tr.position_id = p.id ORDER BY tr.timestamp DESC LIMIT 10").fetchall()
conn.close()

realized = sum(CAPITAL * ((r[1]*100 if r[1] < 1.0 else r[1])/100) * (r[0]/100) for r in trade_rows)
print(f"  UNREALIZED : {total_unrealized:+.2f}$")
print(f"  REALIZED   : {realized:+.2f}$")
print(f"  TOPLAM     : {total_unrealized + realized:+.2f}$")
print(f"  SERMAYE    : {CAPITAL + total_unrealized + realized:.2f}$")

print("\nGECMIS TRADELER:")
print("---------------------------------------")
for r in rows:
    sign = "+" if r[1] > 0 else "-"
    print(f"  [{sign}] {r[0]:<6} {r[1]:+.2f}%  {r[2]}")
