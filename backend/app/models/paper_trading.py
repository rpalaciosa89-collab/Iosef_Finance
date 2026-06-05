"""
Paper Trading Models - SQLAlchemy ORM
Models: PaperAccount, PaperPosition, PaperTrade
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.db.database import Base


class TradeDirection(str, enum.Enum):
    LONG  = "LONG"
    SHORT = "SHORT"


class TradeStatus(str, enum.Enum):
    OPEN   = "OPEN"
    CLOSED = "CLOSED"


class PaperAccount(Base):
    __tablename__ = "paper_accounts"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    name           = Column(String, default="Default Simulation Account")
    initial_balance= Column(Float, default=100_000.0)   # $100K virtual
    cash_balance   = Column(Float, default=100_000.0)
    is_active      = Column(Boolean, default=True)
    created_at     = Column(DateTime, default=datetime.utcnow)

    positions = relationship("PaperPosition", back_populates="account")
    trades    = relationship("PaperTrade",    back_populates="account")


class PaperPosition(Base):
    """An open (live) position in a paper account."""
    __tablename__ = "paper_positions"

    id             = Column(Integer, primary_key=True, index=True)
    account_id     = Column(Integer, ForeignKey("paper_accounts.id"), nullable=False)
    ticker         = Column(String, nullable=False, index=True)
    direction      = Column(Enum(TradeDirection), default=TradeDirection.LONG)
    quantity       = Column(Float, nullable=False)
    entry_price    = Column(Float, nullable=False)
    current_price  = Column(Float, nullable=True)   # mark-to-market
    stop_loss      = Column(Float, nullable=True)
    take_profit    = Column(Float, nullable=True)
    signal_source  = Column(String, default="IOSEF_ML")  # e.g. XGBoost, LSTM, MANUAL
    opened_at      = Column(DateTime, default=datetime.utcnow)

    account  = relationship("PaperAccount", back_populates="positions")


class PaperTrade(Base):
    """A historical (closed) trade record."""
    __tablename__ = "paper_trades"

    id             = Column(Integer, primary_key=True, index=True)
    account_id     = Column(Integer, ForeignKey("paper_accounts.id"), nullable=False)
    ticker         = Column(String, nullable=False)
    direction      = Column(Enum(TradeDirection))
    quantity       = Column(Float)
    entry_price    = Column(Float)
    exit_price     = Column(Float, nullable=True)
    pnl            = Column(Float, nullable=True)          # net P&L in USD
    pnl_pct        = Column(Float, nullable=True)          # % return
    status         = Column(Enum(TradeStatus), default=TradeStatus.OPEN)
    signal_source  = Column(String, default="IOSEF_ML")
    opened_at      = Column(DateTime, default=datetime.utcnow)
    closed_at      = Column(DateTime, nullable=True)
    close_reason   = Column(String, nullable=True)         # TP / SL / MANUAL

    account  = relationship("PaperAccount", back_populates="trades")
