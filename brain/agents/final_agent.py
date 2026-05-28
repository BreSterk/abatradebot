import logging
import json
from .base_agent import BaseAgent
from collectors.models import TradeDecision

logger = logging.getLogger(__name__)

class FinalAgent(BaseAgent):
    def __init__(self):
        super().__init__("FinalAgent", temperature=0.4)

    def analyze(self, ticker: str, signals: list, bullish_output: str, bearish_output: str, context: dict = {}, macro_output: str = "") -> TradeDecision:
        system_prompt = self.load_prompt("final_v1.txt")

        user_message = f"""
Hisse: {ticker}
Market Regime: {context.get('regime', 'bilinmiyor')}
VIX: {context.get('vix', 'bilinmiyor')}
Fed Risk: {context.get('fed_risk', False)}
Earnings Season: {context.get('earnings_season', False)}
Açık Pozisyon Sayısı: {context.get('open_positions', 0)}

BULLISH ANALİST:
{bullish_output}

BEARISH ANALİST:
{bearish_output}

MAKRO ANALİST:
{macro_output}

Önceki Karar: {context.get('previous_decision', 'Yok')}
Not: Önceki kararınla çelişiyorsan çok güçlü gerekçe sun. Tutarsız olma.

Final kararını ver.
"""

        response = self.call_claude(system_prompt, user_message)
        decision = self._parse_response(ticker, response)
        return decision

    def _parse_response(self, ticker: str, response: str) -> TradeDecision:
        try:
            clean = response.strip()
            if "```" in clean:
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]

            data = json.loads(clean)

            return TradeDecision(
                ticker=data.get("ticker", ticker),
                decision=data.get("decision", "WAIT"),
                conviction=float(data.get("conviction", 0.0)),
                uncertainty=float(data.get("uncertainty", 0.5)),
                position_size_pct=float(data.get("position_size_pct", 0.0)),
                thesis=data.get("thesis") or "",
                counter_argument=data.get("counter_argument") or "",
                invalidators=data.get("invalidators") or [],
                time_horizon_days=int(data.get("time_horizon_days") or 0),
                tp_logic=data.get("tp_logic") or "",
                sl_logic=data.get("sl_logic") or "",
                missing_data=data.get("missing_data", ""),
                wait_reason=data.get("wait_reason"),
                agent_outputs={"raw_response": response}
            )

        except Exception as e:
            logger.error(f"FinalAgent parse hatası: {e}\nResponse: {response}")
            return TradeDecision(
                ticker=ticker,
                decision="WAIT",
                conviction=0.0,
                uncertainty=1.0,
                thesis="Parse hatası",
                counter_argument="",
                wait_reason=f"Parse hatası: {e}"
            )