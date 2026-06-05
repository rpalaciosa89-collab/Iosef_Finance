from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from app.services.backtester import Backtester
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()

@router.get("/{ticker}")
def run_backtest(ticker: str, start_date: str = "2023-01-01", end_date: str = "2024-01-01", current_user: User = Depends(get_current_user)):
    try:
        bt = Backtester(ticker, start_date, end_date)
        results = bt.run_strategy()
        return {"data": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
