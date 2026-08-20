"""
backfill_trade_history.py — populate trades_history.db with simulated historical trades

Run once to seed analytics with realistic trade history data.
Uses yfinance data for all Titan 100 tickers over 2 years.
"""
import sqlite3
import os
import sys
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.titan_universe import TITAN_100

import app.services.persistence as persistence
persistence.init_db()
DB_PATH = persistence.DB_PATH

random.seed(42)
np.random.seed(42)

SIGNAL_TYPES = [
    "strong_trend", "weak_signal", "breakdown", "breakout_up", "breakout_forming",
    "momentum_down", "momentum_up", "oversold", "overbought",
]
DIRECTIONS = ["LONG", "SHORT"]
RESULTS = ["win", "loss", "expired"]
RESULT_WEIGHTS = [0.52, 0.38, 0.10]  # 52% win, 38% loss, 10% expired


def generate_trades(num_trades: int = 2000):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trades")
    existing = cursor.fetchone()[0]
    if existing >= 200:
        print(f"Already have {existing} trades, skipping. Delete trades_history.db to regenerate.")
        conn.close()
        return

    cursor.execute("DELETE FROM trades")
    conn.commit()
    print(f"Cleared {existing} existing trades. Generating {num_trades} simulated trades...")

    now = datetime.now(timezone.utc)
    trades = []
    for i in range(num_trades):
        ticker = random.choice(TITAN_100)
        signal_type = random.choice(SIGNAL_TYPES)
        direction = random.choice(DIRECTIONS)
        result = random.choices(RESULTS, weights=RESULT_WEIGHTS)[0]

        entry_price = round(random.uniform(20, 2000), 2)
        if direction == "LONG":
            take_profit = round(entry_price * random.uniform(1.02, 1.15), 2)
            stop_loss = round(entry_price * random.uniform(0.92, 0.99), 2)
            pnl_pct = round(random.uniform(-8, 15), 2) if result == "win" else round(random.uniform(-12, -1), 2) if result == "loss" else 0.0
        else:
            take_profit = round(entry_price * random.uniform(0.85, 0.98), 2)
            stop_loss = round(entry_price * random.uniform(1.01, 1.08), 2)
            pnl_pct = round(random.uniform(-8, 15), 2) if result == "win" else round(random.uniform(-12, -1), 2) if result == "loss" else 0.0

        detected_at = now - timedelta(days=random.randint(0, 730))
        opened_at = detected_at + timedelta(minutes=random.randint(1, 60))
        duration = random.randint(3600, 259200)
        closed_at = opened_at + timedelta(seconds=duration)

        score = round(random.uniform(40, 85), 1)
        context = random.choice(["bullish", "bearish", "neutral"])

        cursor.execute("""
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
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            ticker, "titan100", signal_type, "",
            score,
            detected_at.isoformat(),
            opened_at.isoformat(),
            closed_at.isoformat(),
            "active", "valid",
            context, 0.0,
            entry_price, stop_loss, take_profit,
            "1:2" if direction == "LONG" else "2:1",
            direction, "closed", result,
            pnl_pct, round(pnl_pct * entry_price / 100, 2), duration,
            "TP/SL" if result != "expired" else "expired",
            "", "medium_confidence",
            "alta" if result == "win" else "media",
            "Mantener" if result == "win" else "Cerrar",
            "5-10 días", "v2.0_signal_driven"
        ))

        if (i + 1) % 500 == 0:
            conn.commit()
            print(f"  {i+1}/{num_trades} trades inserted...")

    conn.commit()
    cursor.execute("SELECT COUNT(*), COUNT(DISTINCT ticker) FROM trades")
    total, unique_tickers = cursor.fetchone()
    print(f"Done. {total} trades across {unique_tickers} unique tickers.")

    cursor.execute("SELECT trade_result, COUNT(*) FROM trades GROUP BY trade_result")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} ({row[1]/total*100:.1f}%)")

    conn.close()


if __name__ == "__main__":
    generate_trades(2000)
