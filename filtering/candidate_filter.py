import logging

logger = logging.getLogger(__name__)

MIN_RAW_SCORE = 0.55
MIN_CONFIDENCE = 0.50
MIN_AVG_DOLLAR_VOLUME = 5_000_000
MIN_MARKET_CAP = 500_000_000
FDA_BIOTECH_ENABLED = False

BIOTECH_KEYWORDS = ["therapeutics", "biotech", "pharma", "biopharma", "biosciences", "cervomed", "oncology", "clinical", "trial", "therapeut"]

def is_biotech(ticker: str, company: str = "") -> bool:
    company_lower = company.lower()
    return any(kw in company_lower for kw in BIOTECH_KEYWORDS)

def passes_filter(signal) -> bool:
    # Skor kontrolü
    if signal.raw_score < MIN_RAW_SCORE:
        logger.debug(f"Filtre: {signal.ticker} skor düşük ({signal.raw_score})")
        return False

    if signal.confidence < MIN_CONFIDENCE:
        logger.debug(f"Filtre: {signal.ticker} confidence düşük ({signal.confidence})")
        return False

    # FDA/biotech kontrolü
    if not FDA_BIOTECH_ENABLED:
        company = signal.metadata.get("company", "")
        if is_biotech(signal.ticker, company):
            logger.debug(f"Filtre: {signal.ticker} biotech, devre dışı")
            return False

    return True

def filter_candidates(signals: list) -> list:
    passed = [s for s in signals if passes_filter(s)]
    logger.info(f"Candidate filter: {len(signals)} → {len(passed)} sinyal")
    return passed