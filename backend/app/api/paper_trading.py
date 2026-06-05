"""
Paper Trading API Router
Endpoints:
  POST   /api/paper-trading/account          — Create simulation account
  GET    /api/paper-trading/portfolio         — Full portfolio + PnL
  POST   /api/paper-trading/execute          — Open a simulated position
  POST   /api/paper-trading/close/{position_id} — Close a position
  POST   /api/paper-trading/refresh           — Mark-to-market all positions
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.paper_trading import (
    PaperAccountCreate, PaperAccountResponse,
    ExecuteTradeRequest, PaperPositionResponse,
    PaperTradeResponse, PortfolioSummary
)
from app.services import paper_trading as svc

router = APIRouter()


@router.post("/account", response_model=PaperAccountResponse)
def create_account(
    payload: PaperAccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new paper trading simulation account for the logged-in user."""
    existing = svc.get_account(current_user.id, db)
    if existing:
        raise HTTPException(status_code=400, detail="Active account already exists. Use /portfolio to view it.")
    account = svc.create_account(current_user.id, payload, db)
    return account


@router.get("/portfolio", response_model=PortfolioSummary)
def get_portfolio(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch full portfolio: open positions, trade history, realized/unrealized PnL."""
    try:
        return svc.get_portfolio(current_user.id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/execute", response_model=PaperPositionResponse)
def execute_trade(
    payload: ExecuteTradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Simulate opening a trade position based on an Iosef Finance signal.
    Deducts cost from virtual cash balance.
    """
    try:
        pos = svc.execute_trade(current_user.id, payload, db)
        return pos
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/close/{position_id}", response_model=PaperTradeResponse)
def close_position(
    position_id: int,
    close_reason: str = "MANUAL",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Close an open position. Fetches live price for final PnL calculation."""
    try:
        trade = svc.close_position(current_user.id, position_id, close_reason, db)
        return trade
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/refresh", response_model=list[PaperPositionResponse])
def refresh_positions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark-to-market all open positions with the latest market price.
    Automatically closes positions that hit Stop Loss or Take Profit.
    """
    positions = svc.refresh_positions(current_user.id, db)
    return positions
