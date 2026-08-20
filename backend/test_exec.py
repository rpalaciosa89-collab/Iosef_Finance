from app.models.user import User  # IMPORT FIRST
from app.db.database import SessionLocal
from app.services.paper_trading import execute_trade
from app.schemas.paper_trading import ExecuteTradeRequest
from app.models.paper_trading import TradeDirection

db = SessionLocal()
try:
    req = ExecuteTradeRequest(
        ticker="MCD",
        direction=TradeDirection.LONG,
        quantity=10,
        entry_price=278.90,
        stop_loss=260.0,
        take_profit=310.0,
        signal_source="IOSEF_ML"
    )
    res = execute_trade(user_id=1, payload=req, db=db)
    print("Success:", res)
except Exception as e:
    print("Error:", e)
finally:
    db.close()
