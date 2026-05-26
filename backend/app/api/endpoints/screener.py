from typing import Any, List, Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


class StockScreenerRow(BaseModel):
    ticker: str
    company: str
    sector: str
    industry: str
    country: str
    market_cap: float  # in Millions
    pe_ratio: Optional[float]
    price: float
    change_percent: float
    volume: int


@router.get("/", response_model=List[StockScreenerRow])
def get_screener_data(
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    country: Optional[str] = None,
    min_market_cap: Optional[float] = None,
    pe_filter: Optional[str] = Query(None, description="e.g., 'under_15', 'over_20'"),
    limit: int = 20,
    offset: int = 0
) -> Any:
    """
    Stock screener API mimicking Finviz filtration capabilities.
    """
    # Mock stock database
    mock_stocks = [
        StockScreenerRow(
            ticker="AAPL", company="Apple Inc.", sector="Technology", 
            industry="Consumer Electronics", country="USA", market_cap=2950000.0, 
            pe_ratio=28.5, price=175.50, change_percent=1.2, volume=52000000
        ),
        StockScreenerRow(
            ticker="MSFT", company="Microsoft Corp.", sector="Technology", 
            industry="Software - Infrastructure", country="USA", market_cap=3120000.0, 
            pe_ratio=35.1, price=415.20, change_percent=-0.4, volume=23000000
        ),
        StockScreenerRow(
            ticker="NVDA", company="NVIDIA Corp.", sector="Technology", 
            industry="Semiconductors", country="USA", market_cap=2200000.0, 
            pe_ratio=75.3, price=875.12, change_percent=4.8, volume=41000000
        ),
        StockScreenerRow(
            ticker="AMZN", company="Amazon.com Inc.", sector="Consumer Cyclical", 
            industry="Internet Retail", country="USA", market_cap=1850000.0, 
            pe_ratio=62.4, price=178.15, change_percent=0.8, volume=33000000
        ),
        StockScreenerRow(
            ticker="TSLA", company="Tesla Inc.", sector="Consumer Cyclical", 
            industry="Auto Manufacturers", country="USA", market_cap=550000.0, 
            pe_ratio=42.0, price=172.50, change_percent=-2.1, volume=88000000
        ),
        StockScreenerRow(
            ticker="ASML", company="ASML Holding N.V.", sector="Technology", 
            industry="Semiconductor Equipment", country="Netherlands", market_cap=380000.0, 
            pe_ratio=40.8, price=950.40, change_percent=1.5, volume=1200000
        ),
    ]

    filtered_stocks = mock_stocks

    # Apply filters if provided
    if sector:
        filtered_stocks = [s for s in filtered_stocks if s.sector.lower() == sector.lower()]
    if industry:
        filtered_stocks = [s for s in filtered_stocks if s.industry.lower() == industry.lower()]
    if country:
        filtered_stocks = [s for s in filtered_stocks if s.country.lower() == country.lower()]
    if min_market_cap:
        filtered_stocks = [s for s in filtered_stocks if s.market_cap >= min_market_cap]
    
    if pe_filter:
        if pe_filter == "under_15":
            filtered_stocks = [s for s in filtered_stocks if s.pe_ratio is not None and s.pe_ratio < 15]
        elif pe_filter == "over_20":
            filtered_stocks = [s for s in filtered_stocks if s.pe_ratio is not None and s.pe_ratio > 20]

    return filtered_stocks[offset : offset + limit]
