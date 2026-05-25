import asyncio
import logging
from datetime import datetime
from .base_collector import BaseCollector
from .models import Signal

logger = logging.getLogger(__name__)

class USASpendingCollector(BaseCollector):
    def __init__(self, queue: asyncio.Queue):
        super().__init__("USA_SPENDING", queue)
        self.seen_ids = set()

    async def collect(self):
        url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
        payload = {
            "filters": {
                "time_period": [{"start_date": datetime.utcnow().strftime("%Y-%m-%d"),
                                 "end_date": datetime.utcnow().strftime("%Y-%m-%d")}],
                "award_type_codes": ["A", "B", "C", "D"],
            },
            "fields": ["Recipient Name", "Award Amount", "Awarding Agency Name", "Description"],
            "limit": 50,
            "sort": "Award Amount",
            "order": "desc"
        }

        data = await self.fetch_post(url, payload)
        if not data:
            return

        results = data.get("results", [])
        logger.info(f"USA_SPENDING: {len(results)} ihale bulundu")

        for result in results:
            award_id = result.get("Award ID", "")
            if award_id in self.seen_ids:
                continue
            self.seen_ids.add(award_id)

            recipient = result.get("Recipient Name", "")
            amount = result.get("Award Amount", 0)

            if amount < 10_000_000:  # 10M altı ihale önemsiz
                continue

            signal = Signal(
                ticker="UNKNOWN",
                source="usa_spending",
                category="government_contract",
                raw_score=0.75,
                confidence=0.80,
                event_time=datetime.utcnow(),
                ingestion_time=datetime.utcnow(),
                expected_horizon_hours=168,
                decay_rate=0.03,
                catalyst_type="government_contract",
                raw_text=f"{recipient} - ${amount:,.0f} ihale aldı",
                metadata={
                    "recipient": recipient,
                    "amount": amount,
                    "agency": result.get("Awarding Agency Name", ""),
                    "description": result.get("Description", ""),
                }
            )

            await self.queue.put(signal)
            logger.info(f"USA_SPENDING sinyal: {recipient[:30]} - ${amount:,.0f}")