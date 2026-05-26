import yfinance as yf
import pandas as pd
import numpy as np

tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AVGO", "PEP", "COST", "CSCO", "TMUS", "ADBE", "TXN", "QCOM", "INTC", "AMD", "NFLX", "HON", "INTU"]

# Fetch data from Jan 2025 to give enough history for moving averages
data = yf.download(tickers, start="2025-01-01", end="2026-05-27", progress=False)

closes = data["Close"]
volumes = data["Volume"]

def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

sma50 = closes.rolling(50).mean()
sma200 = closes.rolling(200).mean()
avg_vol_20 = volumes.rolling(20).mean()
rsi = closes.apply(calc_rsi)
pct_change = closes.pct_change() * 100

prev_close = closes.shift(1)
prev_sma50 = sma50.shift(1)
prev_sma200 = sma200.shift(1)

# Market Context
stocks_above_sma50 = (closes > sma50).sum(axis=1)
total_stocks = closes.notna().sum(axis=1)
breadth = stocks_above_sma50 / total_stocks

bullish_days = breadth > 0.6
bearish_days = breadth < 0.4

bullish_mask = pd.DataFrame(index=closes.index, columns=closes.columns)
for col in bullish_mask.columns:
    bullish_mask[col] = bullish_days
    
bearish_mask = pd.DataFrame(index=closes.index, columns=closes.columns)
for col in bearish_mask.columns:
    bearish_mask[col] = bearish_days

# Signal: oversold_bullish (Good entry signal)
is_oversold = rsi < 30
oversold = is_oversold & (~is_oversold.shift(1).fillna(False))
buy_signals = oversold & bullish_mask

# Signal: breakout_vol_1_5 (Another good entry signal)
breakout_up = (prev_close < prev_sma50) & (closes > sma50)
buy_signals_2 = breakout_up & (volumes > (1.5 * avg_vol_20))

# Combine entry signals
entry_signals = buy_signals | buy_signals_2

# Filter for March 2026 to present
start_date = "2026-03-01"
entry_signals = entry_signals.loc[start_date:]
closes_test = closes.loc[start_date:]

# Simulate Trading
initial_capital = 2000.0
capital = initial_capital
positions = {} # ticker: {shares: X, buy_price: Y, date: Z}

trades = []

# Simple holding period strategy: Exit after 5 days or 5% stop loss or 10% take profit
for date in entry_signals.index:
    # Check for exits on current positions
    exits = []
    for t in list(positions.keys()):
        pos = positions[t]
        current_price = closes_test.loc[date, t]
        if np.isnan(current_price):
            continue
            
        ret = (current_price - pos['buy_price']) / pos['buy_price']
        days_held = (date - pos['date']).days
        
        # Exit logic
        if ret >= 0.10 or ret <= -0.05 or days_held >= 5:
            profit = (current_price - pos['buy_price']) * pos['shares']
            capital += pos['shares'] * current_price
            trades.append({
                'Ticker': t,
                'Buy Date': pos['date'].strftime('%Y-%m-%d'),
                'Sell Date': date.strftime('%Y-%m-%d'),
                'Buy Price': pos['buy_price'],
                'Sell Price': current_price,
                'Return %': ret * 100,
                'Profit $': profit
            })
            del positions[t]
    
    # Check for entries
    daily_signals = entry_signals.loc[date]
    active_tickers = daily_signals[daily_signals].index.tolist()
    
    for t in active_tickers:
        if t not in positions and capital > 100:
            price = closes_test.loc[date, t]
            if np.isnan(price):
                continue
                
            # Invest 20% of current capital or all if less
            invest_amount = min(capital * 0.20, capital)
            shares = invest_amount / price
            capital -= invest_amount
            positions[t] = {'shares': shares, 'buy_price': price, 'date': date}

# Close any open positions on the last day
last_date = closes_test.index[-1]
for t in list(positions.keys()):
    pos = positions[t]
    current_price = closes_test.loc[last_date, t]
    if np.isnan(current_price):
        current_price = pos['buy_price']
        
    ret = (current_price - pos['buy_price']) / pos['buy_price']
    profit = (current_price - pos['buy_price']) * pos['shares']
    capital += pos['shares'] * current_price
    trades.append({
        'Ticker': t,
        'Buy Date': pos['date'].strftime('%Y-%m-%d'),
        'Sell Date': last_date.strftime('%Y-%m-%d'),
        'Buy Price': pos['buy_price'],
        'Sell Price': current_price,
        'Return %': ret * 100,
        'Profit $': profit,
        'Note': 'Closed at end'
    })

print(f"Initial Capital: ${initial_capital:.2f}")
print(f"Final Capital:   ${capital:.2f}")
print(f"Total Return:    {((capital/initial_capital)-1)*100:.2f}%")
print(f"Total Trades:    {len(trades)}")

if trades:
    df_trades = pd.DataFrame(trades)
    print("\nTrades Details:")
    print(df_trades.to_string())
    
    win_rate = len(df_trades[df_trades['Profit $'] > 0]) / len(trades)
    print(f"\nWin Rate: {win_rate*100:.2f}%")
