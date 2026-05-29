import asyncio
import logging
import re
from datetime import datetime
from .base_collector import BaseCollector
from .models import Signal

logger = logging.getLogger(__name__)

# Item numaralarına göre önem skoru
ITEM_SCORES = {
    "1.01": 0.85,  # Material Definitive Agreement
    "1.02": 0.80,  # Termination of Material Agreement
    "1.03": 0.80,  # Bankruptcy
    "2.01": 0.85,  # Acquisition/Disposition
    "2.02": 0.90,  # Results of Operations (Earnings)
    "2.03": 0.75,  # Direct Financial Obligation
    "2.04": 0.80,  # Triggering Events
    "2.05": 0.80,  # Cost Associated with Exit
    "2.06": 0.85,  # Material Impairment
    "3.01": 0.70,  # Delisting Notice
    "3.02": 0.70,  # Unregistered Sales
    "4.01": 0.75,  # Auditor Change
    "4.02": 0.75,  # Non-Reliance on Financial Statements
    "5.01": 0.80,  # Change in Control
    "5.02": 0.75,  # Director/Officer Change
    "5.03": 0.70,  # Amendment to Charter
    "5.07": 0.65,  # Shareholder Vote
    "5.08": 0.70,  # Reverse Stock Split
    "6.01": 0.65,  # ABS Informational
    "7.01": 0.45,  # Regulation FD Disclosure (zayıf)
    "8.01": 0.45,  # Other Events (zayıf)
    "9.01": 0.50,  # Financial Statements
}

ITEM_NAMES = {
    "1.01": "Material Agreement",
    "1.02": "Agreement Terminated",
    "2.01": "Acquisition/Disposal",
    "2.02": "Earnings Results",
    "2.03": "Financial Obligation",
    "2.06": "Material Impairment",
    "5.01": "Change in Control",
    "5.02": "Management Change",
    "7.01": "Regulation FD",
    "8.01": "Other Events",
    "9.01": "Financial Statements",
}

WATCHED_FORMS = {
    "8-K":    {"catalyst": "news",        "base_score": 0.70, "horizon": 24,  "decay": 0.20},
    "4":      {"catalyst": "insider_buy", "base_score": 0.80, "horizon": 336, "decay": 0.02},
    "SC 13D": {"catalyst": "insider_buy", "base_score": 0.85, "horizon": 336, "decay": 0.02},
}

def get_item_score(items: list) -> tuple:
    if not items:
        return 0.50, "Unknown"
    scores = [ITEM_SCORES.get(item, 0.50) for item in items]
    best_score = max(scores)
    best_item = items[scores.index(best_score)]
    item_name = ITEM_NAMES.get(best_item, f"Item {best_item}")
    item_names = [ITEM_NAMES.get(i, f"Item {i}") for i in items]
    return best_score, ", ".join(item_names)

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

            # Items bazlı score hesapla
            items = source.get("items", [])
            if form_type == "8-K" and items:
                item_score, item_desc = get_item_score(items)
                # Zayıf itemlar için sinyal gönderme
                if item_score < 0.50:
                    logger.debug(f"SEC: {ticker} zayif item ({item_desc}), atlandi")
                    continue
                final_score = item_score
            else:
                item_desc = ""
                final_score = form_info.get("base_score", 0.70)

            # Filing metnini çek
            filing_text = ""
            try:
                cik = source.get("ciks", [""])[0].lstrip("0")
                acc = source.get("adsh", filing_id)
                if cik and acc:
                    filing_text = await self._fetch_filing_text(acc, cik)
            except Exception as e:
                logger.debug(f"Filing text hatasi: {e}")

            raw_text = f"{form_type} filing: {company}"
            if item_desc:
                raw_text += f"\nKonu: {item_desc}"
            if filing_text:
                raw_text += f"\n\nICERIK:\n{filing_text[:1500]}"

            signal = Signal(
                ticker=ticker,
                source="sec_edgar",
                category=form_type,
                raw_score=final_score,
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
                    "items": items,
                    "item_desc": item_desc,
                    "has_content": bool(filing_text),
                }
            )

            await self.queue.put(signal)
            logger.info(f"SEC sinyal: {ticker} | {form_type} | {item_desc} | skor: {final_score:.2f} | icerik: {'var' if filing_text else 'yok'}")
