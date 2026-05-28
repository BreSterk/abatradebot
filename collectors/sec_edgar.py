import asyncio
import logging
import re
from datetime import datetime
from .base_collector import BaseCollector
from .models import Signal

logger = logging.getLogger(__name__)

WATCHED_FORMS = {
    "8-K":    {"catalyst": "news",        "score": 0.70, "horizon": 24,  "decay": 0.20},
    "4":      {"catalyst": "insider_buy", "score": 0.80, "horizon": 336, "decay": 0.02},
    "SC 13D": {"catalyst": "insider_buy", "score": 0.85, "horizon": 336, "decay": 0.02},
}

class SECEdgarCollector(BaseCollector):
    def __init__(self, queue: asyncio.Queue):
        super().__init__("SEC_EDGAR", queue)
        self.seen_ids = set()

    async def collect(self):
        for form_type in WATCHED_FORMS.keys():
            await self._fetch_filings(form_type)
            await asyncio.sleep(2)

    async def _fetch_filing_text(self, accession_no: str, cik: str) -> str:
        try:
            import aiohttp
            clean_acc = accession_no.replace("-", "")
            clean_cik = str(int(cik))
            url = f"https://www.sec.gov/Archives/edgar/data/{clean_cik}/{clean_acc}/{accession_no}.txt"
            headers = {"User-Agent": "TradingAI/1.0 contact@example.com"}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status == 200:
                        data = await r.text()
                        text = re.sub(r'<[^>]+>', ' ', data)
                        text = re.sub(r'\s+', ' ', text).strip()
                        return text[:2000]
        except Exception as e:
            logger.debug(f"Filing text fetch hatasi: {e}")
        return ""

    async def _fetch_filings(self, form_type: str):
        url = "https://efts.sec.gov/LATEST/search-index"
        params = {
            "q": f'"{form_type}"',
            "forms": form_type,
            "dateRange": "custom",
            "startdt": datetime.utcnow().strftime("%Y-%m-%d"),
            "enddt": datetime.utcnow().strftime("%Y-%m-%d"),
        }

        data = await self.fetch(url, params=params)
        if not data:
            return

        hits = data.get("hits", {}).get("hits", [])
        logger.info(f"SEC: {form_type} icin {len(hits)} filing bulundu")

        for hit in hits:
            filing_id = hit.get("_id", "")
            if filing_id in self.seen_ids:
                continue
            self.seen_ids.add(filing_id)

            source = hit.get("_source", {})

            tickers = source.get("tickers", [])
            if not tickers:
                display_names = source.get("display_names", [])
                if display_names:
                    match = re.search(r'\(([A-Z]{1,5})\)', display_names[0])
                    if match and not match.group(1).startswith("CIK"):
                        tickers = [match.group(1)]

            if not tickers:
                continue

            ticker = tickers[0].upper()
            company = source.get("display_names", [""])[0] if source.get("display_names") else ""
            form_info = WATCHED_FORMS.get(form_type, {})

            filing_text = ""
            if form_type == "8-K":
                try:
                    entity_id = source.get("ciks", [""])[0].lstrip("0")
                    acc = source.get("adsh", filing_id)
                    if entity_id and acc:
                        filing_text = await self._fetch_filing_text(acc, entity_id)
                except Exception as e:
                    logger.debug(f"Filing text hatasi: {e}")

            raw_text = f"{form_type} filing: {company}"
            if filing_text:
                raw_text = f"{form_type} filing: {company}\n\nICERIK:\n{filing_text[:1500]}"

            signal = Signal(
                ticker=ticker,
                source="sec_edgar",
                category=form_type,
                raw_score=form_info.get("score", 0.70),
                confidence=0.90,
                event_time=datetime.utcnow(),
                ingestion_time=datetime.utcnow(),
                expected_horizon_hours=form_info.get("horizon", 24),
                decay_rate=form_info.get("decay", 0.10),
                catalyst_type=form_info.get("catalyst", "news"),
                raw_text=raw_text,
                metadata={
                    "form_type": form_type,
                    "filing_id": filing_id,
                    "company": company,
                    "filed_at": source.get("file_date", ""),
                    "has_content": bool(filing_text),
                }
            )

            await self.queue.put(signal)
            logger.info(f"SEC sinyal: {ticker} ({company[:20]}) - {form_type} | icerik: {'var' if filing_text else 'yok'}")
