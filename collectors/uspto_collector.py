import asyncio
import logging
from datetime import datetime
from .base_collector import BaseCollector
from .models import Signal

logger = logging.getLogger(__name__)

class USPTOCollector(BaseCollector):
    def __init__(self, queue: asyncio.Queue):
        super().__init__("USPTO", queue)
        self.seen_ids = set()

    async def collect(self):
        url = "https://developer.uspto.gov/ibd-api/v1/application/grants"
        params = {
            "dateRangeData.startDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "dateRangeData.endDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "start": 0,
            "rows": 50,
        }

        data = await self.fetch(url, params=params)
        if not data:
            return

        results = data.get("results", [])
        logger.info(f"USPTO: {len(results)} patent bulundu")

        for result in results:
            patent_id = result.get("patentNumber", "")
            if patent_id in self.seen_ids:
                continue
            self.seen_ids.add(patent_id)

            assignee = result.get("assigneeEntityName", "")
            title = result.get("inventionTitle", "")

            if not assignee:
                continue

            signal = Signal(
                ticker="UNKNOWN",
                source="uspto",
                category="patent",
                raw_score=0.60,
                confidence=0.65,
                event_time=datetime.utcnow(),
                ingestion_time=datetime.utcnow(),
                expected_horizon_hours=336,
                decay_rate=0.02,
                catalyst_type="patent",
                raw_text=f"{assignee} - {title}",
                metadata={
                    "patent_id": patent_id,
                    "assignee": assignee,
                    "title": title,
                }
            )

            await self.queue.put(signal)
            logger.info(f"USPTO sinyal: {assignee[:30]} - {title[:40]}")