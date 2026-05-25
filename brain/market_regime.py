import logging
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)

class MarketRegime:
    def __init__(self):
        self.last_check = None
        self.cached_regime = None
        self.cache_minutes = 30

    async def get_regime(self) -> dict:
        # Cache kontrolü
        if self.cached_regime and self.last_check:
            diff = (datetime.utcnow() - self.last_check).seconds / 60
            if diff < self.cache_minutes:
                return self.cached_regime

        regime = await self._fetch_regime()
        self.cached_regime = regime
        self.last_check = datetime.utcnow()
        return regime

    async def _fetch_regime(self) -> dict:
        vix = await self._get_vix()
        
        # VIX'e göre regime belirle
        if vix is None:
            regime = "neutral"
            volatility = "normal"
        elif vix > 30:
            regime = "risk_off"
            volatility = "high"
        elif vix > 20:
            regime = "neutral"
            volatility = "normal"
        else:
            regime = "risk_on"
            volatility = "low"

        # Fed takvimi kontrolü
        fed_risk = self._check_fed_calendar()

        # Earnings season kontrolü
        earnings_season = self._check_earnings_season()

        result = {
            "regime": regime,
            "volatility": volatility,
            "vix": vix or 20,
            "fed_risk": fed_risk,
            "earnings_season": earnings_season,
            "notes": f"VIX: {vix}, Fed: {fed_risk}, Earnings: {earnings_season}"
        }

        logger.info(f"Market Regime: {result}")
        return result

    async def _get_vix(self) -> float:
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
            async with aiohttp.ClientSession() as session:
                headers = {"User-Agent": "TradingAI/1.0 contact@example.com"}
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
                        logger.info(f"VIX: {price}")
                        return float(price)
        except Exception as e:
            logger.error(f"VIX fetch hatası: {e}")
        return None

    def _check_fed_calendar(self) -> bool:
        # FOMC toplantı haftaları (yaklaşık)
        fomc_months = {
            1: [28, 29],
            3: [18, 19],
            5: [6, 7],
            6: [17, 18],
            7: [29, 30],
            9: [16, 17],
            10: [28, 29],
            12: [9, 10],
        }
        now = datetime.utcnow()
        month_dates = fomc_months.get(now.month, [])
        return now.day in month_dates

    def _check_earnings_season(self) -> bool:
        # Earnings season: Ocak, Nisan, Temmuz, Ekim
        now = datetime.utcnow()
        earnings_months = [1, 4, 7, 10]
        return now.month in earnings_months