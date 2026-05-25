import json
import logging
from datetime import datetime
from database.db import get_connection

logger = logging.getLogger(__name__)

class EventStore:
    def save_signal(self, signal):
        try:
            conn = get_connection()
            conn.execute("""
                INSERT OR IGNORE INTO signals 
                (id, ticker, source, category, raw_score, confidence,
                event_time, ingestion_time, expected_horizon_hours,
                decay_rate, catalyst_type, raw_text, metadata)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                signal.id,
                signal.ticker,
                signal.source,
                signal.category,
                signal.raw_score,
                signal.confidence,
                signal.event_time.isoformat(),
                signal.ingestion_time.isoformat(),
                signal.expected_horizon_hours,
                signal.decay_rate,
                signal.catalyst_type,
                signal.raw_text,
                json.dumps(signal.metadata)
            ))
            conn.commit()
            conn.close()
            logger.info(f"Sinyal kaydedildi: {signal.ticker} - {signal.source}")
        except Exception as e:
            logger.error(f"Sinyal kayıt hatası: {e}")

    def save_decision(self, decision):
        try:
            conn = get_connection()
            conn.execute("""
                INSERT OR IGNORE INTO decisions
                (id, ticker, decision, conviction, uncertainty,
                position_size_pct, thesis, counter_argument, invalidators,
                time_horizon_days, tp_logic, sl_logic, missing_data,
                wait_reason, timestamp, agent_outputs)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                decision.id,
                decision.ticker,
                decision.decision,
                decision.conviction,
                decision.uncertainty,
                decision.position_size_pct,
                decision.thesis,
                decision.counter_argument,
                json.dumps(decision.invalidators),
                decision.time_horizon_days,
                decision.tp_logic,
                decision.sl_logic,
                decision.missing_data,
                decision.wait_reason,
                decision.timestamp.isoformat(),
                json.dumps(decision.agent_outputs)
            ))
            conn.commit()
            conn.close()
            logger.info(f"Karar kaydedildi: {decision.ticker} - {decision.decision}")
        except Exception as e:
            logger.error(f"Karar kayıt hatası: {e}")

    def get_recent_signals(self, ticker: str, hours: int = 48):
        try:
            conn = get_connection()
            cursor = conn.execute("""
                SELECT * FROM signals 
                WHERE ticker = ?
                AND event_time >= datetime('now', ?)
                ORDER BY event_time DESC
            """, (ticker, f'-{hours} hours'))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Sinyal okuma hatası: {e}")
            return []

    def get_recent_decisions(self, limit: int = 20):
        try:
            conn = get_connection()
            cursor = conn.execute("""
                SELECT * FROM decisions
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as e:
            logger.error(f"Karar okuma hatası: {e}")
            return []