import sys
import os
sys.path.append(os.path.abspath('backend'))

from backend.app.db.database import SessionLocal
from backend.app.services.paper_trading import get_portfolio

db = SessionLocal()
try:
    port = get_portfolio(1, db)
    print("Open:", len(port.open_positions))
    print("History:", len(port.trade_history))
    print("Total Realized:", port.total_realized_pnl)
except Exception as e:
    print(e)
