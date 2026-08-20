from app.db.database import SessionLocal
from app.services.paper_trading import get_portfolio

db = SessionLocal()
try:
    port = get_portfolio(1, db)
    print(f"Open Positions: {len(port.open_positions)}")
    print(f"Trade History: {len(port.trade_history)}")
    print(f"Cash Balance: {port.account.cash_balance}")
    print(f"Total Realized PnL: {port.total_realized_pnl}")
except Exception as e:
    print(e)
