"""
Paper Trading Service Layer
Handles: account creation, executing simulated trades, 
         mark-to-market PnL, stop-loss/take-profit checks.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models.paper_trading import (
    PaperAccount, PaperPosition, PaperTrade,
    TradeDirection, TradeStatus
)
from app.schemas.paper_trading import (
    PaperAccountCreate, ExecuteTradeRequest,
    PaperPositionResponse, PaperTradeResponse, PortfolioSummary
)
from app.services.market_data import get_cached_bulk_prices


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fetch_live_price(ticker: str) -> Optional[float]:
    """Fetch the latest market price using yfinance (1-day snapshot)."""
    try:
        return get_cached_bulk_prices([ticker]).get(ticker)
    except Exception:
        return None


def _compute_unrealized(pos: PaperPosition, current_price: float) -> tuple[float, float]:
    """Returns (unrealized_pnl_usd, unrealized_pnl_pct)."""
    if pos.direction == TradeDirection.LONG:
        pnl = (current_price - pos.entry_price) * pos.quantity
    else:
        pnl = (pos.entry_price - current_price) * pos.quantity
    pnl_pct = (pnl / (pos.entry_price * pos.quantity)) * 100 if pos.entry_price else 0
    return round(pnl, 2), round(pnl_pct, 4)


# ── Account ───────────────────────────────────────────────────────────────────

def create_account(user_id: int, payload: PaperAccountCreate, db: Session) -> PaperAccount:
    account = PaperAccount(
        user_id=user_id,
        name=payload.name,
        initial_balance=payload.initial_balance,
        cash_balance=payload.initial_balance,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_account(user_id: int, db: Session) -> Optional[PaperAccount]:
    return db.query(PaperAccount).filter(PaperAccount.user_id == user_id, PaperAccount.is_active == True).first()


# ── Execute Trade ─────────────────────────────────────────────────────────────

def execute_trade(user_id: int, payload: ExecuteTradeRequest, db: Session) -> PaperPosition:
    account = get_account(user_id, db)
    if not account:
        raise ValueError("No active paper account found. Create one first.")

    cost = payload.entry_price * payload.quantity
    if cost > account.cash_balance:
        raise ValueError(f"Insufficient cash. Required: ${cost:,.2f}, Available: ${account.cash_balance:,.2f}")

    # Deduct cash and open position
    account.cash_balance = round(account.cash_balance - cost, 2)

    position = PaperPosition(
        account_id=account.id,
        ticker=payload.ticker.upper(),
        direction=payload.direction,
        quantity=payload.quantity,
        entry_price=payload.entry_price,
        current_price=payload.entry_price,
        stop_loss=payload.stop_loss,
        take_profit=payload.take_profit,
        signal_source=payload.signal_source,
    )
    db.add(position)

    # Also record in trade history as OPEN
    trade = PaperTrade(
        account_id=account.id,
        ticker=payload.ticker.upper(),
        direction=payload.direction,
        quantity=payload.quantity,
        entry_price=payload.entry_price,
        signal_source=payload.signal_source,
        status=TradeStatus.OPEN,
    )
    db.add(trade)
    db.commit()
    db.refresh(position)
    return position


# ── Close Position ────────────────────────────────────────────────────────────

def close_position(user_id: int, position_id: int, close_reason: str, db: Session) -> PaperTrade:
    account = get_account(user_id, db)
    position = db.query(PaperPosition).filter(
        PaperPosition.id == position_id,
        PaperPosition.account_id == account.id
    ).first()
    if not position:
        raise ValueError("Position not found or not owned by this account.")

    exit_price = _fetch_live_price(position.ticker) or position.current_price or position.entry_price
    pnl, pnl_pct = _compute_unrealized(position, exit_price)

    # Return cash + PnL to account
    proceeds = (position.entry_price * position.quantity) + pnl
    account.cash_balance = round(account.cash_balance + proceeds, 2)

    # Close matching trade record
    trade = db.query(PaperTrade).filter(
        PaperTrade.account_id == account.id,
        PaperTrade.ticker == position.ticker,
        PaperTrade.status == TradeStatus.OPEN,
    ).order_by(PaperTrade.opened_at.desc()).first()

    if trade:
        trade.exit_price  = exit_price
        trade.pnl         = pnl
        trade.pnl_pct     = pnl_pct
        trade.status      = TradeStatus.CLOSED
        trade.closed_at   = datetime.utcnow()
        trade.close_reason= close_reason

    db.delete(position)
    db.commit()
    if trade:
        db.refresh(trade)
    return trade


# ── Mark-to-Market Update ─────────────────────────────────────────────────────

def refresh_positions(user_id: int, db: Session) -> list[PaperPosition]:
    """Fetch latest prices for all open positions and check SL/TP triggers."""
    account = get_account(user_id, db)
    if not account:
        return []

    positions = db.query(PaperPosition).filter(PaperPosition.account_id == account.id).all()
    auto_closed = []

    # SP-5.2: fetch por LOTE (una llamada con cache para todos los tickers)
    tickers = [p.ticker for p in positions]
    prices = get_cached_bulk_prices(tickers)

    for pos in positions:
        price = prices.get(pos.ticker)
        if price is None:
            continue
        pos.current_price = price

        # SL/TP trigger checks
        if pos.stop_loss and (
            (pos.direction == TradeDirection.LONG  and price <= pos.stop_loss) or
            (pos.direction == TradeDirection.SHORT and price >= pos.stop_loss)
        ):
            auto_closed.append((pos.id, "STOP_LOSS"))
        elif pos.take_profit and (
            (pos.direction == TradeDirection.LONG  and price >= pos.take_profit) or
            (pos.direction == TradeDirection.SHORT and price <= pos.take_profit)
        ):
            auto_closed.append((pos.id, "TAKE_PROFIT"))

    db.commit()

    # Auto-close triggered positions
    for pid, reason in auto_closed:
        try:
            close_position(user_id, pid, reason, db)
        except Exception:
            pass

    return db.query(PaperPosition).filter(PaperPosition.account_id == account.id).all()


# ── Portfolio Summary ─────────────────────────────────────────────────────────

def get_portfolio(user_id: int, db: Session) -> PortfolioSummary:
    from app.schemas.paper_trading import PaperAccountResponse, PortfolioSummary

    account = get_account(user_id, db)
    if not account:
        raise ValueError("No active paper account. Please create one first.")

    positions = db.query(PaperPosition).filter(PaperPosition.account_id == account.id).all()
    trades    = db.query(PaperTrade).filter(PaperTrade.account_id == account.id).order_by(PaperTrade.opened_at.desc()).limit(50).all()

    # ── Build position responses with unrealized PnL ──
    pos_responses = []
    total_unrealized = 0.0
    total_position_cost = 0.0
    for pos in positions:
        price = pos.current_price or pos.entry_price
        pnl_usd, pnl_pct = _compute_unrealized(pos, price)
        total_unrealized += pnl_usd
        total_position_cost += pos.entry_price * pos.quantity
        r = PaperPositionResponse.model_validate(pos)
        r.unrealized_pnl     = pnl_usd
        r.unrealized_pnl_pct = pnl_pct
        pos_responses.append(r)

    # Realized PnL from closed trades
    closed = [t for t in trades if t.status == TradeStatus.CLOSED]
    total_realized = round(sum(t.pnl or 0 for t in closed), 2)

    # Win rate
    winners  = sum(1 for t in closed if (t.pnl or 0) > 0)
    win_rate = round((winners / len(closed) * 100) if closed else 0.0, 2)

    total_equity = round(account.cash_balance + total_position_cost + total_unrealized, 2)

    return PortfolioSummary(
        account=PaperAccountResponse.model_validate(account),
        open_positions=pos_responses,
        trade_history=[PaperTradeResponse.model_validate(t) for t in trades],
        total_equity=total_equity,
        total_unrealized_pnl=round(total_unrealized, 2),
        total_realized_pnl=total_realized,
        win_rate=win_rate,
        total_trades=len(trades),
    )
