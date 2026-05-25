import asyncio
import logging
from datetime import datetime
from .base_collector import BaseCollector
from .models import Signal

logger = logging.getLogger(__name__)

SUBREDDITS = ["wallstreetbets", "investing", "stocks", "options"]

SCORE_THRESHOLD = 100  # Min upvote

class RedditCollector(BaseCollector):
    def __init__(self, queue: asyncio.Queue):
        super().__init__("REDDIT", queue)
        self.seen_ids = set()

    async def collect(self):
        for subreddit in SUBREDDITS:
            await self._fetch_subreddit(subreddit)
            await asyncio.sleep(2)

    async def _fetch_subreddit(self, subreddit: str):
        url = f"https://www.reddit.com/r/{subreddit}/hot.json"
        params = {"limit": 25}

        data = await self.fetch(url, params=params)
        if not data:
            return

        posts = data.get("data", {}).get("children", [])
        logger.info(f"REDDIT: r/{subreddit} için {len(posts)} post bulundu")

        for post in posts:
            post_data = post.get("data", {})
            post_id = post_data.get("id", "")

            if post_id in self.seen_ids:
                continue
            self.seen_ids.add(post_id)

            score = post_data.get("score", 0)
            if score < SCORE_THRESHOLD:
                continue

            title = post_data.get("title", "")
            ticker = self._extract_ticker(title)

            if not ticker:
                continue

            signal = Signal(
                ticker=ticker,
                source=f"reddit_{subreddit}",
                category="social_sentiment",
                raw_score=min(0.55 + (score / 10000), 0.75),
                confidence=0.50,
                event_time=datetime.utcnow(),
                ingestion_time=datetime.utcnow(),
                expected_horizon_hours=12,
                decay_rate=0.40,
                catalyst_type="sentiment",
                raw_text=title,
                metadata={
                    "subreddit": subreddit,
                    "score": score,
                    "url": post_data.get("url", ""),
                    "comments": post_data.get("num_comments", 0),
                }
            )

            await self.queue.put(signal)
            logger.info(f"REDDIT sinyal: {ticker} | {title[:50]} | upvote: {score}")

    def _extract_ticker(self, text: str) -> str:
        import re
        # $AAPL veya AAPL formatını yakala
        matches = re.findall(r'\$([A-Z]{2,5})\b|\b([A-Z]{2,5})\b', text)
        
        # Yaygın İngilizce kelimeleri filtrele
        ignore = {"I", "A", "THE", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", 
                  "CAN", "HER", "WAS", "ONE", "OUR", "OUT", "DAY", "GET",
                  "HAS", "HIM", "HIS", "HOW", "ITS", "NEW", "NOW", "OLD",
                  "SEE", "TWO", "WAY", "WHO", "BOY", "DID", "ITS", "LET",
                  "PUT", "SAY", "SHE", "TOO", "USE", "ATH", "RIP", "IMO",
                  "WSB", "SEC", "IPO", "ETF", "CEO", "CFO", "AI", "EPS",
                  "YOY", "QOQ", "ATH", "DD", "TA", "GDP", "FED", "SPY",
                  "QQQ", "DXY", "VIX"}

        for match in matches:
            ticker = match[0] or match[1]
            if ticker and ticker not in ignore and len(ticker) >= 2:
                return ticker

        return ""