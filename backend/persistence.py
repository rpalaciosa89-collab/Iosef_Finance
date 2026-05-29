import sqlite3
import os
import logging
from typing import Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "trades_history.db")

def init_db():
    """Initializes the SQLite database and creates the trades table if it doesn't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create the trades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            ticker TEXT,
            market TEXT,
            signal_type TEXT,
            human_signal TEXT,
            score_at_detection REAL,
            signal_detected_at TEXT,
            trade_opened_at TEXT,
            trade_closed_at TEXT,
            signal_status_at_detection TEXT,
            entry_window_status_at_detection TEXT,
            market_context_used TEXT,
            signal_context_adjustment REAL,
            entry_price REAL,
            stop_loss REAL,
            take_profit REAL,
            risk_reward_ratio TEXT,
            trade_direction TEXT,
            trade_status TEXT,
            trade_result TEXT,
            pnl_percentage REAL,
            pnl_absolute REAL,
            trade_duration_seconds INTEGER,
            exit_reason TEXT,
            signal_invalid_reason TEXT,
            confidence_text TEXT,
            decision_clarity TEXT,
            suggested_action TEXT,
            holding_period TEXT,
            PRIMARY KEY (ticker, signal_detected_at)
        )
    """)
    conn.commit()
    conn.close()
    logging.info(f"Persistence DB initialized at {DB_PATH}")

def save_closed_trade(data: Dict[str, Any]):
    """
    Saves a closed trade to the database. 
    Uses INSERT OR IGNORE to prevent duplicates based on (ticker, signal_detected_at).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = """
        INSERT OR IGNORE INTO trades (
            ticker, market, signal_type, human_signal, score_at_detection,
            signal_detected_at, trade_opened_at, trade_closed_at,
            signal_status_at_detection, entry_window_status_at_detection,
            market_context_used, signal_context_adjustment,
            entry_price, stop_loss, take_profit, risk_reward_ratio,
            trade_direction, trade_status, trade_result,
            pnl_percentage, pnl_absolute, trade_duration_seconds,
            exit_reason, signal_invalid_reason, confidence_text,
            decision_clarity, suggested_action, holding_period
        ) VALUES (
            :ticker, :market, :signal_type, :human_signal, :score_at_detection,
            :signal_detected_at, :trade_opened_at, :trade_closed_at,
            :signal_status_at_detection, :entry_window_status_at_detection,
            :market_context_used, :signal_context_adjustment,
            :entry_price, :stop_loss, :take_profit, :risk_reward_ratio,
            :trade_direction, :trade_status, :trade_result,
            :pnl_percentage, :pnl_absolute, :trade_duration_seconds,
            :exit_reason, :signal_invalid_reason, :confidence_text,
            :decision_clarity, :suggested_action, :holding_period
        )
    """
    
    # Fill defaults for missing fields to avoid KeyError
    fields = [
        "ticker", "market", "signal_type", "human_signal", "score_at_detection",
        "signal_detected_at", "trade_opened_at", "trade_closed_at",
        "signal_status_at_detection", "entry_window_status_at_detection",
        "market_context_used", "signal_context_adjustment",
        "entry_price", "stop_loss", "take_profit", "risk_reward_ratio",
        "trade_direction", "trade_status", "trade_result",
        "pnl_percentage", "pnl_absolute", "trade_duration_seconds",
        "exit_reason", "signal_invalid_reason", "confidence_text",
        "decision_clarity", "suggested_action", "holding_period"
    ]
    
    params = {field: data.get(field) for field in fields}
    
    try:
        cursor.execute(query, params)
        if cursor.rowcount > 0:
            logging.info(f"✅ Trade persisted successfully: {data.get('ticker')} ({data.get('trade_result')})")
        conn.commit()
    except Exception as e:
        logging.error(f"Error saving trade for {data.get('ticker')}: {e}")
    finally:
        conn.close()

def get_recent_history(limit: int = 50) -> list:
    """Retrieves the most recent closed trades for debugging purposes."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM trades ORDER BY trade_closed_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]
