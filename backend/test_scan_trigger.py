import sys, os
sys.path.append(os.path.abspath('.'))

from app.models.user import User  # IMPORT FIRST
from server import run_scan

results, alerts = run_scan("titan100")
for x in results:
    if x.get("signal_strength_score", 0) >= 70.0:
        print(f"Ticker: {x['ticker']}, Status: {x['signal_status']}, Win: {x['signal_strength_score']}, TradePlan: {x.get('trade_plan')}")
