import logging
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class BullishAgent(BaseAgent):
    def __init__(self):
        super().__init__("BullishAgent", temperature=0.8)

    def analyze(self, ticker: str, signals: list, context: dict = {}) -> dict:
        system_prompt = self.load_prompt("bullish_v1.txt")

        signals_text = "\n".join([
            f"- {s.catalyst_type.upper()} | kaynak: {s.source} | skor: {s.raw_score} | {s.raw_text}"
            for s in signals
        ])

        user_message = f"""
Hisse: {ticker}
Market Regime: {context.get('regime', 'bilinmiyor')}

Sinyaller:
{signals_text}

Bu hisse için en güçlü alım tezini üret.
"""

        response = self.call_claude(system_prompt, user_message)
        logger.info(f"BullishAgent {ticker}: {response[:100]}...")

        return {
            "agent": "bullish",
            "ticker": ticker,
            "output": response
        }