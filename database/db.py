import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "trading.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Sinyaller
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            source TEXT NOT NULL,
            category TEXT NOT NULL,
            raw_score REAL,
            confidence REAL,
            event_time TEXT,
            ingestion_time TEXT,
            expected_horizon_hours INTEGER,
            decay_rate REAL,
            catalyst_type TEXT,
            raw_text TEXT,
            metadata TEXT
        )
    """)

    # Kararlar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            ticker TEXT,
            decision TEXT,
            conviction REAL,
            uncertainty REAL,
            position_size_pct REAL,
            thesis TEXT,
            counter_argument TEXT,
            invalidators TEXT,
            time_horizon_days INTEGER,
            tp_logic TEXT,
            sl_logic TEXT,
            missing_data TEXT,
            wait_reason TEXT,
            timestamp TEXT,
            agent_outputs TEXT
        )
    """)

    # Pozisyonlar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            ticker TEXT,
            entry_price REAL,
            current_price REAL,
            size_pct REAL,
            decision_id TEXT,
            opened_at TEXT,
            invalidators TEXT,
            time_horizon_days INTEGER,
            original_catalyst TEXT,
            status TEXT DEFAULT 'open'
        )
    """)

    # Trade sonuçları
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_results (
            id TEXT PRIMARY KEY,
            position_id TEXT,
            entry_price REAL,
            exit_price REAL,
            pnl_pct REAL,
            duration_hours REAL,
            exit_reason TEXT,
            reflection TEXT,
            decision_quality TEXT,
            outcome_quality TEXT,
            timestamp TEXT
        )
    """)

    # Wait kararları
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS wait_decisions (
            id TEXT PRIMARY KEY,
            ticker TEXT,
            reason TEXT,
            signals_present TEXT,
            regime TEXT,
            timestamp TEXT,
            actual_price_change_pct REAL,
            was_good_wait INTEGER
        )
    """)

    conn.commit()
    conn.close()
    print("Veritabanı hazır.")

if __name__ == "__main__":
    init_db()