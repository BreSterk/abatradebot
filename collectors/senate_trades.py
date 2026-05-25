import asyncio
import logging
from datetime import datetime, timedelta
from .base_collector import BaseCollector
from .models import Signal

logger = logging.getLogger(__name__)

class SenateTradesCollector(BaseCollector):
    def __init__(self, queue: asyncio.Queue):
        super().__init__("SENATE_TRADES", queue)
        self.seen_ids = set()

    async def collect(self):
        await self._fetch_quiver()

    async def _fetch_quiver(self):
        url = "https://api.quiverquant.com/beta/live/congresstrading"
        data = await self.fetch(url)

        if not data:
            logger.warning("SENATE_TRADES: Veri gelmedi")
            return

        logger.info(f"SENATE_TRADES: {len(data)} işlem bulundu")

        cutoff = datetime.utcnow() - timedelta(days=30)
        small_amounts = ["$1K - $15K", "$1,001 - $15,000"]

        for trade in data:
            # Tarih filtresi
            trade_date = trade.get("TransactionDate", trade.get("Date", ""))
            if trade_date:
                try:
                    dt = datetime.strptime(trade_date, "%Y-%m-%d")
                    if dt < cutoff:
                        continue
                except:
                    pass

            senator = trade.get("Representative", trade.get("Senator", "Unknown"))
            ticker = trade.get("Ticker", "").upper().strip()
            trade_type = trade.get("Transaction", "").lower()
            amount = trade.get("Range", "")
            party = trade.get("Party", "")

            # Filtreler
            if not ticker or len(ticker) > 5:
                continue
            if amount in small_amounts or not amount:
                continue
            if "purchase" not in trade_type and "buy" not in trade_type:
                continue

            trade_id = f"{senator}-{ticker}-{trade_date}"
            if trade_id in self.seen_ids:
                continue
            self.seen_ids.add(trade_id)

            signal = Signal(
                ticker=ticker,
                source="senate_trades",
                category="senate_purchase",
                raw_score=0.85,
                confidence=0.90,
                event_time=datetime.utcnow(),
                ingestion_time=datetime.utcnow(),
                expected_horizon_hours=336,
                decay_rate=0.02,
                catalyst_type="insider_buy",
                raw_text=f"{senator} ({party}) {ticker} aldı - {amount}",
                metadata={
                    "senator": senator,
                    "party": party,
                    "transaction": trade_type,
                    "amount": amount,
                    "date": trade_date,
                }
            )

            await self.queue.put(signal)
            logger.info(f"SENATE sinyal: {senator} → {ticker} | {amount}")