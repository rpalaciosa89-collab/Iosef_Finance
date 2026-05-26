import yfinance as yf
import pandas as pd

ticker = "AAPL"
data = yf.download(tickers=ticker, period="1d", interval="1m", progress=False)

data_reset = data.reset_index()
data_reset.columns = [str(c[0]) if isinstance(c, tuple) else str(c) for c in data_reset.columns]

records = []
for _, row in data_reset.iterrows():
    time_col = None
    for col in ["Datetime", "Date", "index", "timestamp"]:
        if col in row:
            time_col = col
            break
            
    dt_val = row[time_col]
    ts = int(dt_val.timestamp())
    
    open_p  = float(row["Open"])
    high_p  = float(row["High"])
    low_p   = float(row["Low"])
    close_p = float(row["Close"])
    vol = int(row.get("Volume", 0))

    if pd.isna(close_p): continue

    records.append({
        "time": ts,
        "open": open_p,
        "high": high_p,
        "low": low_p,
        "close": close_p,
        "volume": vol
    })

print(records[:2])
