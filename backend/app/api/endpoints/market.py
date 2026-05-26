from typing import Any, List
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class MarketSummary(BaseModel):
    index_name: str
    price: float
    change: float
    change_percent: float


class TickerPerformance(BaseModel):
    ticker: str
    price: float
    change_percent: float


class MarketOverview(BaseModel):
    indices: List[MarketSummary]
    top_gainers: List[TickerPerformance]
    top_losers: List[TickerPerformance]


@router.get("/overview", response_model=MarketOverview)
def get_market_overview() -> Any:
    """
    Get top indices and ticker highlights (top gainers and losers).
    """
    return MarketOverview(
        indices=[
            MarketSummary(index_name="S&P 500", price=5300.12, change=24.50, change_percent=0.46),
            MarketSummary(index_name="Nasdaq 100", price=18800.45, change=125.80, change_percent=0.67),
            MarketSummary(index_name="Dow Jones", price=39800.75, change=-45.20, change_percent=-0.11),
        ],
        top_gainers=[
            TickerPerformance(ticker="NVDA", price=875.12, change_percent=4.8),
            TickerPerformance(ticker="AMD", price=168.40, change_percent=3.2),
            TickerPerformance(ticker="AAPL", price=175.50, change_percent=1.2),
        ],
        top_losers=[
            TickerPerformance(ticker="TSLA", price=172.50, change_percent=-2.1),
            TickerPerformance(ticker="INTC", price=30.15, change_percent=-1.8),
            TickerPerformance(ticker="NKE", price=92.40, change_percent=-1.1),
        ]
    )
