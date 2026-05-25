import logging
from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

class MacroAgent(BaseAgent):
    def __init__(self):
        super().__init__("MacroAgent", temperature=0.2)

    def analyze(self, ticker: str, signals: list, context: dict = {}) -> dict:
        system_prompt = self.load_prompt("macro_v1.txt")

        signals_text = "\n".join([
            f"- {s.catalyst_type.upper()} | kaynak: {s.source} | skor: {s.raw_score} | {s.raw_text}"
            for s in signals
        ])

        user_message = f"""
Hisse: {ticker}
Market Regime: {context.get('regime', 'bilinmiyor')}
VIX: {context.get('vix', 'bilinmiyor')}
SPY Trend: {context.get('spy_trend', 'bilinmiyor')}
Fed Risk: {context.get('fed_risk', False)}
Earnings Season: {context.get('earnings_season', False)}

Sinyaller:
{signals_text}

Makro risk değerlendirmesi yap.
"""

        response = self.call_claude(system_prompt, user_message)
        logger.info(f"MacroAgent {ticker}: {response[:100]}...")

        return {
            "agent": "macro",
            "ticker": ticker,
            "output": response
        }