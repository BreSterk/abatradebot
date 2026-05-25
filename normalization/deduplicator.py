import hashlib
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class Deduplicator:
    def __init__(self, window_minutes: int = 30):
        self.seen = {}  # hash -> timestamp
        self.window = timedelta(minutes=window_minutes)

    def _hash(self, signal) -> str:
        key = f"{signal.ticker}:{signal.catalyst_type}:{signal.source}"
        return hashlib.md5(key.encode()).hexdigest()

    def is_duplicate(self, signal) -> bool:
        now = datetime.utcnow()

        # Eski kayıtları temizle
        self.seen = {
            h: t for h, t in self.seen.items()
            if now - t < self.window
        }

        h = self._hash(signal)

        if h in self.seen:
            logger.debug(f"Duplicate atlandı: {signal.ticker} | {signal.catalyst_type}")
            return True

        self.seen[h] = now
        return False

    def filter(self, signals: list) -> list:
        unique = []
        for s in signals:
            if not self.is_duplicate(s):
                unique.append(s)
        logger.info(f"Dedup: {len(signals)} → {len(unique)} sinyal")
        return unique