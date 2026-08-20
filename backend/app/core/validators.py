import re

TICKER_PATTERN = re.compile(r"^[A-Za-z0-9\.\-]{1,10}$")

def validate_ticker(ticker: str) -> str:
    if not TICKER_PATTERN.match(ticker):
        raise ValueError(f"Invalid ticker format: {ticker}")
    return ticker.upper()
