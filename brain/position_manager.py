import logging
import uuid
import json
from datetime import datetime, timedelta
from database.db import get_connection

logger = logging.getLogger(__name__)

PAPER_CAPITAL = 10000.0  # Sanal sermaye

class PositionManager:
    def __init__(self):
        pass

    def open_position(self, decision, entry_price: float):
        """BUY kararında pozisyon aç"""
        conn = get_connection()
        position_id = str(uuid.uuid4())[:8]
        
        size_pct = decision.position_size_pct or 5.0
        # Agent 0.05-0.15 arasi deger verirse gercekte % demek, duzelt
        if size_pct < 1.0:
            size_pct = size_pct * 100
        # Max %15, min %3
        size_pct = max(3.0, min(15.0, size_pct))
        dollar_amount = PAPER_CAPITAL * (size_pct / 100)
        shares = dollar_amount / entry_price if entry_price > 0 else 0
        
        conn.execute("""
            INSERT INTO positions 
            (id, ticker, entry_price, current_price, size_pct, decision_id, 
             opened_at, invalidators, time_horizon_days, original_catalyst, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
        """, (
            position_id,
            decision.ticker,
            entry_price,
            entry_price,
            size_pct,
            decision.ticker,
            datetime.utcnow().isoformat(),
            json.dumps(decision.invalidators or []),
            decision.time_horizon_days or 5,
            decision.thesis[:200] if decision.thesis else "",
        ))
        conn.commit()
        conn.close()
        
        logger.info(f"POZİSYON AÇILDI: {decision.ticker} | giriş: ${entry_price:.2f} | tutar: ${dollar_amount:.0f} ({size_pct}%) | {shares:.2f} adet")
        return position_id


    def _update_peak_pnl(self, position_id: str, peak_pnl: float):
        conn = get_connection()
        conn.execute("UPDATE positions SET peak_pnl = ? WHERE id = ?", (peak_pnl, position_id))
        conn.commit()
        conn.close()
    def get_open_positions(self):
        conn = get_connection()
        rows = conn.execute("SELECT * FROM positions WHERE status = 'open'").fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_price(self, ticker: str, current_price: float):
        conn = get_connection()
        conn.execute("UPDATE positions SET current_price = ? WHERE ticker = ? AND status = 'open'", (current_price, ticker))
        conn.commit()
        conn.close()

    def close_position(self, position_id: str, exit_price: float, reason: str):
        conn = get_connection()
        pos = conn.execute("SELECT * FROM positions WHERE id = ?", (position_id,)).fetchone()
        
        if not pos:
            conn.close()
            return

        pos = dict(pos)
        entry_price = pos["entry_price"]
        size_pct = pos["size_pct"]
        dollar_amount = PAPER_CAPITAL * (size_pct / 100)
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100
        pnl_dollar = dollar_amount * (pnl_pct / 100)
        
        opened_at = datetime.fromisoformat(pos["opened_at"])
        duration_hours = (datetime.utcnow() - opened_at).total_seconds() / 3600

        conn.execute("UPDATE positions SET status = 'closed' WHERE id = ?", (position_id,))
        conn.execute("""
            INSERT INTO trade_results
            (id, position_id, entry_price, exit_price, pnl_pct, duration_hours, exit_reason, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4())[:8], position_id, entry_price, exit_price,
            pnl_pct, duration_hours, reason, datetime.utcnow().isoformat(),
        ))
        conn.commit()
        conn.close()

        emoji = "✅" if pnl_pct > 0 else "❌"
        logger.info(f"{emoji} POZİSYON KAPANDI: {pos['ticker']} | PnL: {pnl_pct:+.2f}% ({pnl_dollar:+.0f}$) | Sebep: {reason}")
        from brain.notifier import notify_sell
        notify_sell(pos['ticker'], pnl_pct, reason, entry_price, exit_price)
        return pnl_pct

    def check_exits(self, current_prices: dict):
        from datetime import datetime
        import pytz
        et = pytz.timezone('America/New_York')
        now = datetime.now(et)
        if now.weekday() >= 5:
            return  # Hafta sonu TP/SL kontrolü yapma

        # VIX > 30 ise tüm pozisyonları kapat
        try:
            import yfinance as yf
            vix_data = yf.Ticker("^VIX").history(period="1d")
            vix = float(vix_data["Close"].iloc[-1]) if not vix_data.empty else 20
            if vix >= 30:
                logger.warning(f"VIX {vix:.1f} >= 30, tüm pozisyonlar kapatılıyor!")
                positions = self.get_open_positions()
                for pos in positions:
                    ticker = pos["ticker"]
                    if ticker in current_prices:
                        self.close_position(pos["id"], current_prices[ticker], f"VIX_RISK_OFF_{vix:.0f}")
                return
        except Exception as e:
            logger.debug(f"VIX check hatasi: {e}")

        positions = self.get_open_positions()
        for pos in positions:
            ticker = pos["ticker"]
            if ticker not in current_prices:
                continue
            current_price = current_prices[ticker]
            entry_price = pos["entry_price"]
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            self.update_price(ticker, current_price)

            # Trailing stop seviyeleri
            # 8'e ulaşınca 4'ü koru, 12'ye ulaşınca 7'yi koru, 15'e ulaşınca 10'u koru
            peak_pnl = pos.get("peak_pnl", pnl_pct)
            if pnl_pct > peak_pnl:
                peak_pnl = pnl_pct
                self._update_peak_pnl(pos["id"], peak_pnl)

            trailing_sl = None
            if peak_pnl >= 15:
                trailing_sl = 10.0
            elif peak_pnl >= 12:
                trailing_sl = 7.0
            elif peak_pnl >= 8:
                trailing_sl = 4.0

            if trailing_sl is not None and pnl_pct <= trailing_sl:
                self.close_position(pos["id"], current_price, f"TRAILING_STOP_{trailing_sl:.0f}")
                continue

            # Sabit TP +15%
            if pnl_pct >= 15:
                self.close_position(pos["id"], current_price, "TP_HIT")
                continue

            # Sabit SL -7%
            if pnl_pct <= -7:
                self.close_position(pos["id"], current_price, "SL_HIT")
                continue

            opened_at = datetime.fromisoformat(pos["opened_at"])
            horizon_days = pos.get("time_horizon_days", 5)
            if datetime.utcnow() > opened_at + timedelta(days=horizon_days):
                self.close_position(pos["id"], current_price, "TIME_EXIT")
                continue

            dollar_amount = PAPER_CAPITAL * (pos["size_pct"] / 100)
            pnl_dollar = dollar_amount * (pnl_pct / 100)
            trail_info = f" | peak: {peak_pnl:+.1f}% | trailing_sl: {trailing_sl}%" if trailing_sl else ""
            logger.info(f"POZİSYON: {ticker} | PnL: {pnl_pct:+.2f}% ({pnl_dollar:+.0f}$){trail_info}")

    def get_stats(self):
        conn = get_connection()
        results = conn.execute("SELECT * FROM trade_results").fetchall()
        open_pos = conn.execute("SELECT COUNT(*) as c FROM positions WHERE status='open'").fetchone()
        conn.close()
        
        if not results:
            return {"toplam_trade": 0, "açık_pozisyon": open_pos["c"], "sermaye": f"${PAPER_CAPITAL:.0f}"}
        
        pnls = [r["pnl_pct"] for r in results]
        kazanan = sum(1 for p in pnls if p > 0)
        toplam_pnl_pct = sum(pnls)
        # Dolar hesabi: her trade icin gercek size_pct kullan
        conn2 = get_connection()
        trade_details = conn2.execute('''
            SELECT tr.pnl_pct, p.size_pct FROM trade_results tr
            JOIN positions p ON tr.position_id = p.id
        ''').fetchall()
        conn2.close()
        toplam_pnl_dollar = sum(
            PAPER_CAPITAL * ((row[1]*100 if row[1] < 1.0 else row[1]) / 100) * (row[0] / 100)
            for row in trade_details
        )
        guncel_sermaye = PAPER_CAPITAL + toplam_pnl_dollar
        
        return {
            "toplam_trade": len(pnls),
            "açık_pozisyon": open_pos["c"],
            "kazanma_oranı": f"{kazanan/len(pnls)*100:.0f}%",
            "ortalama_pnl": f"{sum(pnls)/len(pnls):+.2f}%",
            "toplam_pnl": f"{toplam_pnl_pct:+.2f}% ({toplam_pnl_dollar:+.0f}$)",
            "güncel_sermaye": f"${guncel_sermaye:.0f}",
            "en_iyi": f"{max(pnls):+.2f}%",
            "en_kötü": f"{min(pnls):+.2f}%",
        }
