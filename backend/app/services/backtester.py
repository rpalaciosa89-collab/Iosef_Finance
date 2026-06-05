import yfinance as yf
import pandas as pd
import numpy as np

class Backtester:
    def __init__(self, ticker: str, start_date: str, end_date: str):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.data = None

    def fetch_data(self):
        df = yf.download(self.ticker, start=self.start_date, end=self.end_date, progress=False)
        if df.empty:
            raise ValueError(f"No data found for {self.ticker}")
        self.data = df
        return df

    def run_strategy(self, threshold_score: float = 60.0):
        # A mock simulation of PnL since we don't have historical neural scores daily stored yet
        # We simulate that a neural score above threshold would have triggered a buy
        # Here we just use a simple MA crossover as a proxy for backtesting demonstration
        
        if self.data is None:
            self.fetch_data()
            
        df = self.data.copy()
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        df['SMA_20'] = df['Close'].rolling(window=20).mean()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        
        # Signal: 1 (Buy) when SMA_20 > SMA_50, else 0
        df['Signal'] = np.where(df['SMA_20'] > df['SMA_50'], 1, 0)
        df['Position'] = df['Signal'].shift(1)
        
        # Calculate Returns
        df['Daily_Return'] = df['Close'].pct_change()
        df['Strategy_Return'] = df['Position'] * df['Daily_Return']
        
        cumulative_return = (1 + df['Strategy_Return'].fillna(0)).cumprod()
        total_return_pct = (cumulative_return.iloc[-1] - 1) * 100
        
        # Max Drawdown
        running_max = cumulative_return.cummax()
        drawdown = (cumulative_return - running_max) / running_max
        max_drawdown_pct = drawdown.min() * 100
        
        # Sharpe Ratio (annualized)
        daily_volatility = df['Strategy_Return'].std()
        if daily_volatility == 0 or pd.isna(daily_volatility):
            sharpe_ratio = 0
        else:
            sharpe_ratio = (df['Strategy_Return'].mean() / daily_volatility) * np.sqrt(252)

        return {
            "ticker": self.ticker,
            "total_return_pct": round(total_return_pct, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "sharpe_ratio": round(sharpe_ratio, 2)
        }
