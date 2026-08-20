import sqlite3
import os

# SP-6.1: analytics lee de la MISMA DB unificada que persistence/SQLAlchemy
from app.services.persistence import DB_PATH

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def compute_metrics(row):
    total = row["total_trades"]
    wins = row["wins"]
    losses = row["losses"]
    expired = row["expired"]
    
    # Base Rates
    win_rate = (wins / total) if total > 0 else 0
    loss_rate = (losses / total) if total > 0 else 0
    expiry_rate = (expired / total) if total > 0 else 0
    
    # Effective Win Rate (ignoring expirations)
    resolved_trades = wins + losses
    effective_win_rate = (wins / resolved_trades) if resolved_trades > 0 else 0
    
    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "expired": expired,
        "win_rate": round(win_rate * 100, 2),
        "loss_rate": round(loss_rate * 100, 2),
        "expiry_rate": round(expiry_rate * 100, 2),
        "effective_win_rate": round(effective_win_rate * 100, 2),
        "avg_pnl": round(row["avg_pnl"] or 0, 2),
        "avg_duration_minutes": round((row["avg_duration"] or 0) / 60, 1)
    }

def get_signal_analytics():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            signal_type,
            COUNT(*) as total_trades,
            SUM(CASE WHEN trade_result = 'win' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN trade_result = 'loss' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN trade_result = 'expired' THEN 1 ELSE 0 END) as expired,
            AVG(pnl_percentage) as avg_pnl,
            AVG(trade_duration_seconds) as avg_duration
        FROM trades
        WHERE trade_result IN ('win', 'loss', 'expired')
          AND system_version != 'v1.0_legacy'
        GROUP BY signal_type
        ORDER BY total_trades DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    results = {}
    for r in rows:
        results[r["signal_type"]] = compute_metrics(r)
    return results

def get_asset_analytics():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            ticker,
            COUNT(*) as total_trades,
            SUM(CASE WHEN trade_result = 'win' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN trade_result = 'loss' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN trade_result = 'expired' THEN 1 ELSE 0 END) as expired,
            AVG(pnl_percentage) as avg_pnl,
            AVG(trade_duration_seconds) as avg_duration
        FROM trades
        WHERE trade_result IN ('win', 'loss', 'expired')
          AND system_version != 'v1.0_legacy'
        GROUP BY ticker
        HAVING total_trades >= 5
        ORDER BY total_trades DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    results = {}
    for r in rows:
        results[r["ticker"]] = compute_metrics(r)
    return results

def get_context_analytics():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            market_context_used,
            COUNT(*) as total_trades,
            SUM(CASE WHEN trade_result = 'win' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN trade_result = 'loss' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN trade_result = 'expired' THEN 1 ELSE 0 END) as expired,
            AVG(pnl_percentage) as avg_pnl,
            AVG(trade_duration_seconds) as avg_duration
        FROM trades
        WHERE trade_result IN ('win', 'loss', 'expired')
          AND system_version != 'v1.0_legacy'
        GROUP BY market_context_used
        ORDER BY total_trades DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    results = {}
    for r in rows:
        context_name = r["market_context_used"] or "Unknown"
        results[context_name] = compute_metrics(r)
    return results

def generate_narrative_summary(signals, assets, contexts):
    narratives = []
    
    # 1. Evaluate top performing signals (strict definition: > 5 trades, high effective win rate)
    for sig, stats in signals.items():
        if stats["total_trades"] >= 5:
            if stats["effective_win_rate"] >= 60.0 and stats["avg_pnl"] > 0:
                narratives.append(f"La señal '{sig}' tiene un win rate efectivo del {stats['effective_win_rate']}% con {stats['total_trades']} operaciones registradas.")
            if stats["expiry_rate"] >= 50.0:
                narratives.append(f"Advertencia: '{sig}' presenta una tasa de expiración del {stats['expiry_rate']}%, generando ruido operativo.")
    
    # 2. Evaluate context
    for ctx, stats in contexts.items():
        if stats["total_trades"] >= 5 and ctx != "Unknown":
            if stats["effective_win_rate"] >= 55.0:
                narratives.append(f"El contexto '{ctx}' ha propiciado un win rate efectivo del {stats['effective_win_rate']}%.")
                
    # 3. Best / Worst assets (we already filter by min 5 trades in query)
    sorted_assets_by_wr = sorted(assets.items(), key=lambda x: x[1]["effective_win_rate"], reverse=True)
    if sorted_assets_by_wr:
        best_ticker, best_stats = sorted_assets_by_wr[0]
        narratives.append(f"El activo {best_ticker} lidera el win rate efectivo con un {best_stats['effective_win_rate']}% en {best_stats['total_trades']} operaciones.")
        
    sorted_assets_by_exp = sorted(assets.items(), key=lambda x: x[1]["expiry_rate"], reverse=True)
    if sorted_assets_by_exp:
        worst_ticker, worst_stats = sorted_assets_by_exp[0]
        if worst_stats["expiry_rate"] > 40.0:
            narratives.append(f"El activo {worst_ticker} presenta la mayor tasa de expiración ({worst_stats['expiry_rate']}%).")
            
    if not narratives:
        narratives.append("Datos insuficientes para generar conclusiones estadísticas robustas (> 5 operaciones mínimas requeridas).")
        
    return narratives

def build_analytics_payload():
    signals = get_signal_analytics()
    assets = get_asset_analytics()
    contexts = get_context_analytics()
    
    # Build rankings based on the fetched dictionaries
    rankings = {
        "top_signals_by_wr": sorted([{"name": k, **v} for k, v in signals.items() if v["total_trades"] >= 5], key=lambda x: x["effective_win_rate"], reverse=True)[:5],
        "top_assets_by_wr": sorted([{"name": k, **v} for k, v in assets.items()], key=lambda x: x["effective_win_rate"], reverse=True)[:5],
        "high_expiry_signals": sorted([{"name": k, **v} for k, v in signals.items() if v["total_trades"] >= 5], key=lambda x: x["expiry_rate"], reverse=True)[:5]
    }
    
    summary = generate_narrative_summary(signals, assets, contexts)
    
    return {
        "signal_analytics": signals,
        "asset_analytics": assets,
        "context_analytics": contexts,
        "rankings": rankings,
        "summary_text": summary
    }
