import sys
import os
sys.path.append(os.getcwd())
from app.models.user import User
from app.db.database import SessionLocal
from app.services.paper_trading import close_position

db = SessionLocal()
try:
    trade = close_position(user_id=1, position_id=1, close_reason="TEST_CLOSE", db=db)
    print("Trade closed:", trade.status if trade else "None")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
