import sqlite3
import os
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

# SP-6.1: unificacion de persistencia — los trades se guardan en la MISMA DB
# que SQLAlchemy (backend/iosef_finance.db), eliminando el archivo legacy
# backend/data/trades_history.db como fuente de verdad paralela.
from app.db.database import DATABASE_URL

if DATABASE_URL.startswith("sqlite"):
    _db_file = DATABASE_URL.replace("sqlite:///", "").replace("./", "")
    DB_PATH = os.path.join(os.getcwd(), _db_file) if not os.path.isabs(_db_file) else _db_file
else:
    # Postgres: usar archivo local de trades como fallback (migrar luego a tabla SQLAlchemy)
    DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "trades_history.db")

def init_db():
    """Initializes the SQLite database, creates the trades table, and cleans up invalid/TEST records."""
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
            system_version TEXT DEFAULT 'v2.0_signal_driven',
            PRIMARY KEY (ticker, signal_detected_at)
        )
    """)
    
    # Clean up legacy invalid/TEST records to maintain database integrity
    cursor.execute("""
        DELETE FROM trades 
        WHERE ticker IS NULL 
           OR ticker = 'TEST' 
           OR entry_price IS NULL OR entry_price <= 0
           OR stop_loss IS NULL OR stop_loss <= 0
           OR take_profit IS NULL OR take_profit <= 0
           OR trade_opened_at IS NULL OR trade_opened_at = ''
           OR trade_closed_at IS NULL OR trade_closed_at = ''
    """)
    deleted_rows = cursor.rowcount
    if deleted_rows > 0:
        logging.info(f"🧹 Database Cleanup: Removed {deleted_rows} invalid/testing records from trades table.")
        
    conn.commit()
    conn.close()
    logging.info(f"Persistence DB initialized at {DB_PATH}")

def normalize_to_iso(val) -> str:
    """Normalizes any input timestamp (float, int, or string) to a standard ISO 8601 string."""
    if not val:
        return ""
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val, tz=timezone.utc).isoformat()
    if isinstance(val, str):
        val_str = val.strip()
        if "T" in val_str:
            return val_str
        # If it's a numeric Unix timestamp string
        try:
            num = float(val_str)
            return datetime.fromtimestamp(num, tz=timezone.utc).isoformat()
        except ValueError:
            pass
        return val_str
    return ""

def save_closed_trade(data: Dict[str, Any]):
    """
    Saves a closed trade to the database. 
    Rigorously validates fields and normalizes dates before saving.
    """
    ticker = data.get("ticker")
    entry_price = data.get("entry_price")
    stop_loss = data.get("stop_loss")
    take_profit = data.get("take_profit")
    trade_opened_at = data.get("trade_opened_at")
    trade_closed_at = data.get("trade_closed_at")

    # PART 1 — VALIDATION EN BACKEND (CRÍTICO)
    # 1. No guardar si es ticker de pruebas o incompleto
    if not ticker or ticker.strip().upper() == "TEST":
        logging.warning("⚠️ Trade save skipped: Ticker is invalid or 'TEST'")
        return

    # 2. Validar precios críticos
    try:
        entry_price = float(entry_price) if entry_price is not None else 0.0
        stop_loss = float(stop_loss) if stop_loss is not None else 0.0
        take_profit = float(take_profit) if take_profit is not None else 0.0
    except (ValueError, TypeError):
        logging.warning(f"⚠️ Trade save skipped for {ticker}: Non-numeric pricing data.")
        return

    if entry_price <= 0.0 or stop_loss <= 0.0 or take_profit <= 0.0:
        logging.warning(f"⚠️ Trade save skipped for {ticker}: Critical prices must be positive. Entry: {entry_price}, SL: {stop_loss}, TP: {take_profit}")
        return

    # 3. Validar fechas de apertura y cierre
    norm_opened = normalize_to_iso(trade_opened_at)
    norm_closed = normalize_to_iso(trade_closed_at)
    norm_detected = normalize_to_iso(data.get("signal_detected_at") or trade_opened_at)

    if not norm_opened or not norm_closed:
        logging.warning(f"⚠️ Trade save skipped for {ticker}: Missing or invalid opening/closing timestamps.")
        return

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
            decision_clarity, suggested_action, holding_period, system_version
        ) VALUES (
            :ticker, :market, :signal_type, :human_signal, :score_at_detection,
            :signal_detected_at, :trade_opened_at, :trade_closed_at,
            :signal_status_at_detection, :entry_window_status_at_detection,
            :market_context_used, :signal_context_adjustment,
            :entry_price, :stop_loss, :take_profit, :risk_reward_ratio,
            :trade_direction, :trade_status, :trade_result,
            :pnl_percentage, :pnl_absolute, :trade_duration_seconds,
            :exit_reason, :signal_invalid_reason, :confidence_text,
            :decision_clarity, :suggested_action, :holding_period, :system_version
        )
    """
    
    fields = [
        "market", "signal_type", "human_signal", "score_at_detection",
        "signal_status_at_detection", "entry_window_status_at_detection",
        "market_context_used", "signal_context_adjustment",
        "risk_reward_ratio", "trade_direction", "trade_status", "trade_result",
        "pnl_percentage", "pnl_absolute", "trade_duration_seconds",
        "exit_reason", "signal_invalid_reason", "confidence_text",
        "decision_clarity", "suggested_action", "holding_period", "system_version"
    ]
    
    params = {field: data.get(field) for field in fields}
    params["ticker"] = ticker
    params["entry_price"] = entry_price
    params["stop_loss"] = stop_loss
    params["take_profit"] = take_profit
    params["signal_detected_at"] = norm_detected
    params["trade_opened_at"] = norm_opened
    params["trade_closed_at"] = norm_closed
    if not params.get("system_version"):
        params["system_version"] = "v2.0_signal_driven"
    
    try:
        cursor.execute(query, params)
        if cursor.rowcount > 0:
            logging.info(f"✅ Trade persisted successfully: {ticker} ({data.get('trade_result')})")
        conn.commit()
    except Exception as e:
        logging.error(f"Error saving trade for {ticker}: {e}")
    finally:
        conn.close()

def get_closed_trades_history(limit: int = 50, offset: int = 0, include_legacy: bool = False) -> List[Dict[str, Any]]:
    """
    Retrieves the history of closed trades, ordered by closed time descending.
    PART 2 — FILTRO EN GET /api/history (excluye registros incompletos o de prueba).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    legacy_filter = "" if include_legacy else "AND system_version != 'v1.0_legacy'"

    query = f"""
        SELECT * FROM trades 
        WHERE ticker IS NOT NULL AND ticker != 'TEST'
          AND entry_price IS NOT NULL AND entry_price > 0
          AND stop_loss IS NOT NULL AND stop_loss > 0
          AND take_profit IS NOT NULL AND take_profit > 0
          AND trade_opened_at IS NOT NULL AND trade_opened_at != ''
          AND trade_closed_at IS NOT NULL AND trade_closed_at != ''
          {legacy_filter}
        ORDER BY trade_closed_at DESC 
        LIMIT ? OFFSET ?
    """
    cursor.execute(query, (limit, offset))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

