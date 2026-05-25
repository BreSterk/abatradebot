import logging
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class BearishAgent(BaseAgent):
    def __init__(self):
        super().__init__("BearishAgent", temperature=0.3)

    def analyze(self, ticker: str, signals: list, context: dict = {}) -> dict:
        system_prompt = self.load_prompt("bearish_v1.txt")

        signals_text = "\n".join([
            f"- {s.catalyst_type.upper()} | kaynak: {s.source} | skor: {s.raw_score} | {s.raw_text}"
            for s in signals
        ])

        user_message = f"""
Hisse: {ticker}
Market Regime: {context.get('regime', 'bilinmiyor')}

Sinyaller:
{signals_text}

Bu trade için en güçlü karşı argümanı üret.
"""

        response = self.call_claude(system_prompt, user_message)
        logger.info(f"BearishAgent {ticker}: {response[:100]}...")

        return {
            "agent": "bearish",
            "ticker": ticker,
            "output": response
        }