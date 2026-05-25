import asyncio
import logging
import os
from datetime import datetime
from .base_collector import BaseCollector
from .models import Signal

logger = logging.getLogger(__name__)
AV_KEY = os.getenv("ALPHAVANTAGE_KEY", "")
WATCHLIST = ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","SPY","QQQ","T","CARR","BAH","DVN"]

class AlphaVantageCollector(BaseCollector):
    def __init__(self, queue: asyncio.Queue):
        super().__init__("ALPHAVANTAGE", queue)
        self.seen_ids = set()

    async def collect(self):
        if not AV_KEY:
            logger.warning("ALPHAVANTAGE_KEY eksik")
            return
        for ticker in WATCHLIST:
            await self._fetch_news(ticker)
            await asyncio.sleep(15)

    async def _fetch_news(self, ticker: str):
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={ticker}&limit=5&apikey={AV_KEY}"
        data = await self.fetch_json(url)
        if not data or "feed" not in data:
            return
        feed = data["feed"]
        logger.info(f"ALPHAVANTAGE: {ticker} icin {len(feed)} haber")
        for item in feed:
            item_id = item.get("url", "")
            if item_id in self.seen_ids:
                continue
            self.seen_ids.add(item_id)
            title = item.get("title", "")
            summary = item.get("summary", "")
            sentiment = 0.65
            for ts in item.get("ticker_sentiment", []):
                if ts.get("ticker") == ticker:
                    try:
                        score = float(ts.get("ticker_sentiment_score", 0))
                        relevance = float(ts.get("relevance_score", 0))
                        if relevance > 0.5:
                            sentiment = min(0.95, 0.65 + abs(score) * 0.3)
                    except:
                        pass
            signal = Signal(
                ticker=ticker,
                source="alphavantage",
                category="news",
                raw_score=sentiment,
                confidence=0.70,
                event_time=datetime.utcnow(),
                ingestion_time=datetime.utcnow(),
                expected_horizon_hours=24,
                decay_rate=0.20,
                catalyst_type="news",
                raw_text=f"{title} {summary}"[:500],
                metadata={"source": "alphavantage", "url": item_id}
            )
            await self.queue.put(signal)
            logger.info(f"ALPHAVANTAGE sinyal: {ticker} | {title[:60]}")
