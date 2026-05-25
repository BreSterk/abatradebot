import asyncio
import logging
from datetime import datetime
from .base_collector import BaseCollector
from .models import Signal

logger = logging.getLogger(__name__)

# Ücretsiz RSS haber kaynakları
NEWS_FEEDS = [
    {
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline",
        "source": "yahoo_finance",
        "score": 0.65
    },
    {
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "source": "reuters",
        "score": 0.70
    },
    {
        "url": "https://feeds.marketwatch.com/marketwatch/topstories",
        "source": "marketwatch",
        "score": 0.65
    },
]

class NewsCollector(BaseCollector):
    def __init__(self, queue: asyncio.Queue):
        super().__init__("NEWS", queue)
        self.seen_ids = set()

    async def collect(self):
        for feed in NEWS_FEEDS:
            await self._fetch_feed(feed)
            await asyncio.sleep(2)

    async def _fetch_feed(self, feed: dict):
        data = await self.fetch_xml(feed["url"])
        if not data:
            return

        items = data.get("items", [])
        logger.info(f"NEWS: {feed['source']} için {len(items)} haber bulundu")

        for item in items:
            item_id = item.get("link", "")
            if item_id in self.seen_ids:
                continue
            self.seen_ids.add(item_id)

            title = item.get("title", "")
            ticker = self._extract_ticker(title)

            if not ticker:
                continue

            signal = Signal(
                ticker=ticker,
                source=feed["source"],
                category="news",
                raw_score=feed["score"],
                confidence=0.65,
                event_time=datetime.utcnow(),
                ingestion_time=datetime.utcnow(),
                expected_horizon_hours=24,
                decay_rate=0.20,
                catalyst_type="news",
                raw_text=title,
                metadata={
                    "source": feed["source"],
                    "link": item_id,
                    "pubDate": item.get("pubDate", ""),
                }
            )

            await self.queue.put(signal)
            logger.info(f"NEWS sinyal: {ticker} | {title[:50]}")

    def _extract_ticker(self, text: str) -> str:
        import re
        matches = re.findall(r'\$([A-Z]{2,5})\b', text)
        if matches:
            return matches[0]

        # Parantez içi ticker: "(AAPL)"
        matches = re.findall(r'\(([A-Z]{2,5})\)', text)
        ignore = {"CEO", "CFO", "IPO", "ETF", "SEC", "FBI", "CIA", "USA",
                  "NYSE", "NASDAQ", "USD", "EUR", "GDP", "CPI", "FED"}
        for m in matches:
            if m not in ignore:
                return m

        return ""