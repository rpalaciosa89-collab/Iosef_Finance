"""
Paper Trading Schemas (Pydantic V2)
"""
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime
from app.models.paper_trading import TradeDirection, TradeStatus
from app.core.validators import validate_ticker


# ── Account ──────────────────────────────────────────────────────────────────
class PaperAccountCreate(BaseModel):
    name: str = "Default Simulation Account"
    initial_balance: float = 100_000.0


class PaperAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:              int
    name:            str
    initial_balance: float
    cash_balance:    float
    is_active:       bool
    created_at:      datetime


# ── Execute Trade ─────────────────────────────────────────────────────────────
class ExecuteTradeRequest(BaseModel):
    ticker:         str
    direction:      TradeDirection = TradeDirection.LONG
    quantity:       float                    # shares to simulate
    entry_price:    float                    # last known price from screener
    stop_loss:      Optional[float] = None
    take_profit:    Optional[float] = None
    signal_source:  str = "IOSEF_ML"

    @field_validator("ticker")
    @classmethod
    def _validate_ticker(cls, v: str) -> str:
        return validate_ticker(v)


# ── Position ──────────────────────────────────────────────────────────────────
class PaperPositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:            int
    ticker:        str
    direction:     TradeDirection
    quantity:      float
    entry_price:   float
    current_price: Optional[float]
    stop_loss:     Optional[float]
    take_profit:   Optional[float]
    signal_source: str
    opened_at:     datetime

    # Computed fields (injected by service layer)
    unrealized_pnl:     Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None


# ── Trade History ─────────────────────────────────────────────────────────────
class PaperTradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:           int
    ticker:       str
    direction:    TradeDirection
    quantity:     float
    entry_price:  float
    exit_price:   Optional[float]
    pnl:          Optional[float]
    pnl_pct:      Optional[float]
    status:       TradeStatus
    signal_source:str
    opened_at:    datetime
    closed_at:    Optional[datetime]
    close_reason: Optional[str]


# ── Portfolio Summary ─────────────────────────────────────────────────────────
class PortfolioSummary(BaseModel):
    account:            PaperAccountResponse
    open_positions:     List[PaperPositionResponse]
    trade_history:      List[PaperTradeResponse]
    total_equity:       float    # cash + unrealized P&L
    total_unrealized_pnl: float
    total_realized_pnl:   float
    win_rate:             float  # % of closed trades that were profitable
    total_trades:         int
