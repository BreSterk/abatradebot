
def is_market_open():
    from datetime import datetime
    import pytz
    et = pytz.timezone('America/New_York')
    now = datetime.now(et)
    if now.weekday() >= 5:  # Cumartesi=5, Pazar=6
        return False
    market_open = now.replace(hour=9, minute=30, second=0)
    market_close = now.replace(hour=16, minute=0, second=0)
    return market_open <= now <= market_close

import asyncio
import logging
import os
from datetime import datetime

def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, f"trading_{datetime.now().strftime('%Y%m%d')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )

async def analysis_loop(queue_manager, event_store):
    logger = logging.getLogger("analysis")
    from brain.agents.bullish_agent import BullishAgent
    from brain.agents.bearish_agent import BearishAgent
    from brain.agents.macro_agent import MacroAgent
    from brain.agents.final_agent import FinalAgent
    from brain.market_regime import MarketRegime
    from brain.position_manager import PositionManager
    import yfinance as yf

    bullish = BullishAgent()
    bearish = BearishAgent()
    macro = MacroAgent()
    final = FinalAgent()
    regime_checker = MarketRegime()
    position_manager = PositionManager()

    while True:
        await asyncio.sleep(60)

        # Açık pozisyonları kontrol et
        try:
            open_positions = position_manager.get_open_positions()
            if open_positions:
                prices = {}
                for p in open_positions:
                    try:
                        hist = yf.Ticker(p["ticker"]).history(period="1d")
                        if not hist.empty:
                            prices[p["ticker"]] = float(hist["Close"].iloc[-1])
                    except:
                        pass
                position_manager.check_exits(prices)
        except Exception as e:
            logger.error(f"Pozisyon kontrol hatası: {e}")

        if not is_market_open():
            logger.info("Piyasa kapalı, analiz bekleniyor...")
            await asyncio.sleep(60)
            continue
        candidates = queue_manager.get_candidates()
        if not candidates:
            logger.info("Analiz edilecek candidate yok, bekleniyor...")
            continue

        logger.info(f"{len(candidates)} candidate bulundu")

        regime = await regime_checker.get_regime()

        if regime.get("volatility") == "extreme":
            logger.warning("Extreme volatility! Sistem durduruldu.")
            continue

        context = {
            "regime": regime.get("regime", "neutral"),
            "vix": regime.get("vix", 20),
            "spy_trend": "unknown",
            "fed_risk": regime.get("fed_risk", False),
            "earnings_season": regime.get("earnings_season", False),
            "open_positions": len(position_manager.get_open_positions())
        }

        for candidate in candidates[:1]:
            ticker = candidate["ticker"]
            signals = candidate["signals"]

            logger.info(f"Analiz başlıyor: {ticker} | {len(signals)} sinyal | regime: {regime.get('regime')}")

            bullish_result = bullish.analyze(ticker, signals, context)
            bearish_result = bearish.analyze(ticker, signals, context)
            macro_result = macro.analyze(ticker, signals, context)

            from database.db import get_connection
            conn = get_connection()
            prev = conn.execute(
                "SELECT decision, conviction, wait_reason FROM decisions WHERE ticker=? ORDER BY timestamp DESC LIMIT 1",
                (ticker,)
            ).fetchone()
            conn.close()
            if prev:
                pass  # previous_decision kaldirildi

            decision = final.analyze(
                ticker, signals,
                bullish_result["output"],
                bearish_result["output"],
                context,
                macro_output=macro_result["output"]
            )

            logger.info(f"KARAR: {ticker} | {decision.decision} | conviction: {decision.conviction}")
            if decision.decision == "BUY":
                logger.info(f"  Tez: {decision.thesis}")
                logger.info(f"  Karşı: {decision.counter_argument}")
            else:
                logger.info(f"  Neden WAIT: {decision.wait_reason}")

            # BUY kararında pozisyon aç
            EXCLUDED = {"SPY", "QQQ", "IWM", "DIA", "VTI", "VOO"}
            if decision.decision == "BUY" and decision.conviction >= 0.65 and ticker not in EXCLUDED:
                try:
                    # SPY gunluk filtre
                    import yfinance as yf
                    _spy = yf.Ticker("SPY").history(period="2d")
                    if len(_spy) >= 2:
                        _spy_chg = (_spy["Close"].iloc[-1] - _spy["Close"].iloc[-2]) / _spy["Close"].iloc[-2] * 100
                        if _spy_chg <= -1.0:
                            logger.info(f"SPY {_spy_chg:.2f}% <= -1%, pozisyon acilmiyor")
                            event_store.save_decision(decision)
                            queue_manager.mark_analyzed(ticker)
                            continue
                    # Gunluk zarar limiti
                    from database.db import get_connection as _gc
                    _conn = _gc()
                    _pos = _conn.execute("SELECT entry_price, current_price, size_pct FROM positions WHERE status='open'").fetchall()
                    _conn.close()
                    _daily_pnl = sum(10000*((r[2]*100 if r[2]<1.0 else r[2])/100)*((r[1]-r[0])/r[0]) for r in _pos if r[0]>0)
                    if _daily_pnl <= -200:
                        logger.info(f"Gunluk zarar -200$ asild ({_daily_pnl:.0f}$), pozisyon acilmiyor")
                        event_store.save_decision(decision)
                        queue_manager.mark_analyzed(ticker)
                        continue
                    # Max pozisyon kontrolu
                    open_count = len(position_manager.get_open_positions())
                    if open_count >= 20:
                        logger.info(f"Max pozisyon (20) doldu, {ticker} atlanıyor")
                    else:
                        # VIX kontrolu
                        import yfinance as yf
                        vix_data = yf.Ticker("^VIX").history(period="1d")
                        vix = float(vix_data["Close"].iloc[-1]) if not vix_data.empty else 20
                        if vix >= 25:
                            logger.info(f"VIX {vix:.1f} >= 25, yeni pozisyon açılmıyor")
                        else:
                            # Conviction'a gore position size
                            conv = decision.conviction
                            if conv >= 0.85:
                                decision.position_size_pct = 4.0
                            elif conv >= 0.75:
                                decision.position_size_pct = 2.0
                            else:
                                decision.position_size_pct = 1.0

                            ticker_info = yf.Ticker(ticker).info
                            market_cap = ticker_info.get("marketCap", 0) or 0
                            avg_vol = ticker_info.get("averageVolume", 0) or 0
                            price = ticker_info.get("currentPrice", 1) or 1
                            dollar_vol = avg_vol * price
                            if market_cap > 5_000_000_000:
                                logger.info(f"{ticker} ${market_cap/1e9:.1f}B > $5B, atlaniyor")
                            elif market_cap < 200_000_000:
                                logger.info(f"{ticker} ${market_cap/1e6:.0f}M < $200M, atlaniyor")
                            elif dollar_vol < 3_000_000:
                                logger.info(f"{ticker} hacim ${dollar_vol/1e6:.1f}M < $3M, atlaniyor")
                            else:
                                hist = yf.Ticker(ticker).history(period="1d")
                                if not hist.empty:
                                    entry_price = float(hist["Close"].iloc[-1])
                                    position_manager.open_position(decision, entry_price)
                                    from brain.notifier import notify_buy
                                    notify_buy(ticker, decision.conviction, decision.thesis, entry_price)
                                    logger.info(f"Pozisyon açıldı: {ticker} | size: %{decision.position_size_pct} | VIX: {vix:.1f}")
                except Exception as e:
                    logger.error(f"Pozisyon açma hatası: {e}")

            event_store.save_decision(decision)
            queue_manager.mark_analyzed(ticker)

async def queue_listener(queue, queue_manager, event_store):
    logger = logging.getLogger("queue")
    from normalization.deduplicator import Deduplicator
    from filtering.candidate_filter import passes_filter

    dedup = Deduplicator(window_minutes=30)

    while True:
        signal = await queue.get()

        # Deduplication
        if dedup.is_duplicate(signal):
            continue

        # Candidate filter
        if not passes_filter(signal):
            continue

        logger.info(f"SİNYAL: {signal.ticker} | {signal.catalyst_type} | skor: {signal.raw_score}")
        event_store.save_signal(signal)
        queue_manager.add_signal(signal)

async def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Piyasa kapali ise bekle
    while not is_market_open():
        import datetime
        import pytz
        et = pytz.timezone('America/New_York')
        now = datetime.datetime.now(et)
        logger.info(f"Piyasa kapali ({now.strftime('%A %H:%M')} ET), bekleniyor...")
        await asyncio.sleep(300)
    
    logger.info("Trading AI başlatılıyor...")

    from database.db import init_db
    init_db()

    from research.event_store import EventStore
    from brain.queue_manager import QueueManager

    event_store = EventStore()
    queue_manager = QueueManager()
    queue = asyncio.Queue()

    # Collectors
    from collectors.sec_edgar import SECEdgarCollector
    from collectors.fed_fomc import FedFomcCollector
    from collectors.usa_spending import USASpendingCollector
    from collectors.reddit_collector import RedditCollector
    from collectors.news_collector import NewsCollector
    from collectors.alphavantage_collector import AlphaVantageCollector
    from collectors.uspto_collector import USPTOCollector
    from collectors.senate_trades import SenateTradesCollector

    sec = SECEdgarCollector(queue)
    fed = FedFomcCollector(queue)
    usa = USASpendingCollector(queue)
    reddit = RedditCollector(queue)
    news = NewsCollector(queue)
    av = AlphaVantageCollector(queue)
    uspto = USPTOCollector(queue)
    senate = SenateTradesCollector(queue)

    logger.info("Tüm collector'lar başlatıldı")

    await asyncio.gather(
        sec.run(interval_seconds=300),
        fed.run(interval_seconds=600),
        usa.run(interval_seconds=900),
        reddit.run(interval_seconds=300),
        news.run(interval_seconds=300),
        av.run(interval_seconds=300),
        uspto.run(interval_seconds=3600),
        senate.run(interval_seconds=3600),
        queue_listener(queue, queue_manager, event_store),
        analysis_loop(queue_manager, event_store)
    )

if __name__ == "__main__":
    asyncio.run(main())