import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Kaynak ağırlıkları
TIER_1_SOURCES = {"senate_trades", "sec_edgar_form4", "usa_spending"}
TIER_2_SOURCES = {"sec_edgar", "fed_fomc", "earnings"}
TIER_3_SOURCES = {"reddit_wallstreetbets", "reddit_investing", "reddit_stocks", 
                   "reddit_options", "news", "marketwatch", "yahoo_finance"}

TIER_1_CATEGORIES = {"senate_purchase", "insider_buy", "government_contract"}
TIER_2_CATEGORIES = {"news", "fed_announcement", "earnings_beat"}
TIER_3_CATEGORIES = {"social_sentiment", "sentiment"}

def get_tier(signal) -> int:
    if signal.source in TIER_1_SOURCES or signal.category in TIER_1_CATEGORIES:
        return 1
    if signal.source in TIER_2_SOURCES or signal.category in TIER_2_CATEGORIES:
        return 2
    return 3

def calculate_priority(signals: list) -> float:
    tier1 = [s for s in signals if get_tier(s) == 1]
    tier2 = [s for s in signals if get_tier(s) == 2]
    tier3 = [s for s in signals if get_tier(s) == 3]

    # Tier 1 tek başına yeterli
    if tier1:
        score = 100 + (len(tier1) * 20)
        score += len(tier2) * 10
        score += len(tier3) * 2
        return score

    # 2x Tier 2 yeterli
    if len(tier2) >= 2:
        score = 50 + (len(tier2) * 10)
        score += len(tier3) * 2
        return score

    # Tier 2 + Tier 3 kombinasyonu
    if len(tier2) >= 1 and len(tier3) >= 2:
        score = 30 + (len(tier2) * 10) + (len(tier3) * 2)
        return score

    # Sadece Tier 3 → analiz etme
    return 0

class QueueManager:
    def __init__(self):
        self.signal_groups = defaultdict(list)
        self.last_analysis = {}

    def add_signal(self, signal):
        self.signal_groups[signal.ticker].append(signal)
        tier = get_tier(signal)
        logger.info(f"Queue'ya eklendi: {signal.ticker} | tier: {tier} | toplam: {len(self.signal_groups[signal.ticker])}")

    def get_candidates(self):
        candidates = []
        now = datetime.utcnow()

        for ticker, signals in self.signal_groups.items():
            # Son 2 saatte analiz edildiyse geç
            last = self.last_analysis.get(ticker)
            if last and (now - last).total_seconds() < 7200:
                continue

            priority = calculate_priority(signals)

            # Öncelik 0 ise analiz etme
            if priority == 0:
                continue

            tier1 = [s for s in signals if get_tier(s) == 1]
            tier2 = [s for s in signals if get_tier(s) == 2]
            tier3 = [s for s in signals if get_tier(s) == 3]

            candidates.append({
                "ticker": ticker,
                "signals": signals,
                "signal_count": len(signals),
                "priority": priority,
                "tier1_count": len(tier1),
                "tier2_count": len(tier2),
                "tier3_count": len(tier3),
            })

            logger.debug(f"Candidate: {ticker} | priority: {priority:.0f} | T1:{len(tier1)} T2:{len(tier2)} T3:{len(tier3)}")

        # Önceliğe göre sırala
        candidates.sort(key=lambda x: x["priority"], reverse=True)

        if candidates:
            logger.info(f"Top candidates: {[(c['ticker'], c['priority']) for c in candidates[:5]]}")

        return candidates

    def mark_analyzed(self, ticker):
        self.last_analysis[ticker] = datetime.utcnow()
        self.signal_groups[ticker] = []

    def get_stats(self):
        total = len(self.signal_groups)
        candidates = self.get_candidates()
        return {
            "total_tickers": total,
            "total_signals": sum(len(s) for s in self.signal_groups.values()),
            "pending_analysis": len(candidates),
            "top_candidate": candidates[0]["ticker"] if candidates else None,
        }