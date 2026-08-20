"""
SP-6.1: Verifica que la persistencia de trades usa la DB unificada
(la misma que SQLAlchemy), no archivos legacy duplicados.
"""
import os

from app.db.database import DATABASE_URL
from app.services.persistence import DB_PATH as PERSISTENCE_DB_PATH


def test_persistence_uses_unified_db():
    """El DB_PATH de persistence apunta a la misma DB que SQLAlchemy."""
    db_file = DATABASE_URL.replace("sqlite:///", "").replace("./", "")
    assert db_file in PERSISTENCE_DB_PATH, (
        f"persistence usa {PERSISTENCE_DB_PATH}, pero SQLAlchemy usa {DATABASE_URL}"
    )


def test_trades_table_exists_in_unified_db():
    """La tabla trades existe en la DB unificada (con WAL)."""
    import sqlite3

    from app.services.persistence import init_db
    init_db()

    db_file = DATABASE_URL.replace("sqlite:///", "").replace("./", "")
    conn = sqlite3.connect(db_file)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='trades'"
    ).fetchall()
    conn.close()
    assert len(rows) == 1, "la tabla trades no existe en la DB unificada"


def test_init_db_is_idempotent():
    """init_db() se puede llamar multiples veces sin errores."""
    from app.services.persistence import init_db
    init_db()
    init_db()
    init_db()


def test_record_trade_roundtrip():
    """Guardar un trade y recuperarlo del historial funciona contra la DB unificada."""
    from app.services.persistence import init_db, save_closed_trade, get_closed_trades_history

    init_db()
    save_closed_trade(
        {
            "ticker": "TEST-UNIFY",
            "market": "titan100",
            "signal_type": "breakout_up",
            "human_signal": "Test",
            "entry_price": 100.0,
            "stop_loss": 95.0,
            "take_profit": 110.0,
            "trade_direction": "LONG",
            "trade_opened_at": "2026-08-01T10:00:00Z",
            "trade_closed_at": "2026-08-02T10:00:00Z",
        }
    )
    history = get_closed_trades_history(limit=50)
    tickers = {t["ticker"] for t in history}
    assert "TEST-UNIFY" in tickers