import asyncio
import logging
from datetime import datetime
from .base_collector import BaseCollector
from .models import Signal

logger = logging.getLogger(__name__)

class FedFomcCollector(BaseCollector):
    def __init__(self, queue: asyncio.Queue):
        super().__init__("FED_FOMC", queue)
        self.seen_ids = set()

    async def collect(self):
        url = "https://www.federalreserve.gov/feeds/press_all.xml"
        data = await self.fetch_xml(url)
        if not data:
            return

        items = data.get("items", [])
        logger.info(f"FED: {len(items)} haber bulundu")

        for item in items:
            item_id = item.get("link", "")
            if item_id in self.seen_ids:
                continue
            self.seen_ids.add(item_id)

            signal = Signal(
                ticker="SPY",
                source="fed_fomc",
                category="fed_announcement",
                raw_score=0.85,
                confidence=0.95,
                event_time=datetime.utcnow(),
                ingestion_time=datetime.utcnow(),
                expected_horizon_hours=48,
                decay_rate=0.10,
                catalyst_type="macro",
                raw_text=item.get("title", ""),
                metadata={"link": item_id}
            )

            await self.queue.put(signal)
            logger.info(f"FED sinyal: {item.get('title', '')[:50]}")