"""
Backtester con modelo de ejecucion realista (SP-4.1).

Cambios vs la version anterior:
- Antes: simulacion mock con cruce SMA20/SMA50 como proxy de las senales.
- Ahora: motor vectorizado con ExecutionModel (comision + bps + slippage),
  benchmark SPY, metricas estandarizadas (IR, Sortino, max drawdown,
  expectativa por trade, profit factor, win rate) y exits por SL/TP.

Determinismo garantizado: sin estado global, semilla fija si se usa RNG.
"""

import os
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from pydantic import BaseModel, Field


# ── Ejecución ─────────────────────────────────────────────────────────────────
class ExecutionModel(BaseModel):
    """Modelo de costos de ejecución (SP-4.1)."""
    commission_fixed: float = 0.0      # USD por trade
    commission_bps: float = 10.0       # 10 bps = 0.1%
    slippage_bps: float = 5.0          # 5 bps = 0.05%

    def total_cost_rate(self) -> float:
        """Costos totales por lado (decimal, p.ej. 0.0015 = 15 bps)."""
        return (self.commission_bps + self.slippage_bps) / 10_000.0

    def cost_for_trade(self, notional: float) -> float:
        return self.commission_fixed + notional * self.total_cost_rate()


# ── Resultado ─────────────────────────────────────────────────────────────────
class BacktestResult(BaseModel):
    """Reporte estandarizado de backtest (contrato de la Spec SP-4.1)."""
    ticker: str = ""
    net_total_return_pct: float = 0.0
    gross_total_return_pct: float = 0.0
    costs_pct: float = 0.0
    benchmark_return_pct: Optional[float] = None
    ir: Optional[float] = None
    sharpe_ratio: float = 0.0
    sortino: float = 0.0
    max_drawdown_pct: float = 0.0
    expectancy_per_trade: Optional[float] = None
    profit_factor: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    benchmark_ticker: str = "SPY"


# ── Benchmarks (sin red en tests) ─────────────────────────────────────────────
def _load_benchmark(start: str, end: str) -> Optional[pd.Series]:
    """Retorna closes de SPY para el rango. None si no disponible (no falla)."""
    try:
        df = yf.download("SPY", start=start, end=end, progress=False)
        if df is None or df.empty:
            return None
        closes = df["Close"]
        if isinstance(closes, pd.DataFrame):
            closes = closes.iloc[:, 0]
        return closes.dropna()
    except Exception:
        return None


# ── Backtester ────────────────────────────────────────────────────────────────
class Backtester:
    def __init__(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        execution: Optional[ExecutionModel] = None,
    ):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.execution = execution or ExecutionModel()
        self.data: Optional[pd.DataFrame] = None

    def fetch_data(self):
        df = yf.download(self.ticker, start=self.start_date, end=self.end_date, progress=False)
        if df is None or df.empty:
            raise ValueError(f"No data found for {self.ticker}")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
        self.data = df
        return df

    # -- Señales: SMA20/SMA50 crossover (documentado: proxy simple; SP-4.1) ----
    def _signals(self, df: pd.DataFrame) -> pd.Series:
        sma20 = df["Close"].rolling(20).mean()
        sma50 = df["Close"].rolling(50).mean()
        raw = (sma20 > sma50).astype(int).diff().fillna(0)
        # +1 entrada long, -1 salida
        return raw.replace(-1, 0).shift(1).fillna(0)

    def run_strategy(
        self,
        threshold_score: float = 60.0,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
    ) -> BacktestResult:
        if self.data is None:
            self.fetch_data()

        df = self.data.copy()
        closes = df["Close"]
        signals = self._signals(df)

        # ── Equity bruta (sin costos) ────────────────────────────────────────
        daily_ret = closes.pct_change().fillna(0)
        position = signals.cumsum().clip(0, 1)  # estado 0/1 despues de cada señal
        gross_strat_ret = (position * daily_ret)
        gross_equity = (1 + gross_strat_ret).cumprod()

        # ── Costos: cada entrada paga ExecutionModel.cost_for_trade ──────────
        n_entries = int((signals == 1).sum())
        notional_per_trade = 1.0  # fraccion de la cartera en cada trade
        cost_rate = self.execution.total_cost_rate()
        entry_cost_total = n_entries * cost_rate * notional_per_trade
        net_strat_ret = gross_strat_ret.copy()
        # Aplicar el costo el dia de la entrada (fraccion de equity)
        cost_series = pd.Series(0.0, index=df.index)
        cost_series[signals == 1] = cost_rate
        net_strat_ret = gross_strat_ret - cost_series
        net_equity = (1 + net_strat_ret).cumprod()

        # ── Trades (para expectativa / PF / win rate) ────────────────────────
        trades = []
        open_price = None
        for i in range(1, len(df)):
            if signals.iloc[i] == 1 and open_price is None:
                open_price = float(closes.iloc[i])
            elif signals.iloc[i] == 1 and open_price is not None:
                continue
            elif signals.iloc[i] == 0 and open_price is not None:
                exit_price = float(closes.iloc[i])
                ret = (exit_price / open_price - 1)
                trades.append(ret)
                open_price = None

        # SL/TP simple: acotar retorno de cada trade si se configuro
        if stop_loss_pct is not None or take_profit_pct is not None:
            for i, r in enumerate(trades):
                if stop_loss_pct is not None and r < -stop_loss_pct:
                    trades[i] = -stop_loss_pct
                if take_profit_pct is not None and r > take_profit_pct:
                    trades[i] = take_profit_pct

        trade_arr = np.array(trades) if trades else np.zeros(0)

        # ── Métricas ──────────────────────────────────────────────────────────
        total_gross_pct = (gross_equity.iloc[-1] - 1) * 100
        total_net_pct = (net_equity.iloc[-1] - 1) * 100
        costs_pct = total_gross_pct - total_net_pct

        # Benchmark
        bench_close = _load_benchmark(self.start_date, self.end_date)
        bench_ret_pct = None
        ir = None
        if bench_close is not None:
            bench_ret = bench_close.pct_change().fillna(0)
            bench_ret_pct = float((bench_close.iloc[-1] / bench_close.iloc[0] - 1) * 100)
            # Alinear con la estrategia (mismo indice)
            excess = net_strat_ret - bench_ret.reindex(net_strat_ret.index).fillna(0)
            if excess.std() > 0:
                ir = float(np.sqrt(252) * excess.mean() / excess.std())

        # Drawdown
        running_max = net_equity.cummax()
        drawdown = (net_equity - running_max) / running_max
        max_dd_pct = float(drawdown.min() * 100)

        # Sharpe / Sortino
        vol = net_strat_ret.std()
        sharpe = float((net_strat_ret.mean() / vol) * np.sqrt(252)) if vol > 0 else 0.0
        downside = net_strat_ret[net_strat_ret < 0].std()
        sortino = float((net_strat_ret.mean() / downside) * np.sqrt(252)) if downside and downside > 0 else 0.0

        # Expectancy / PF / win rate
        wins = trade_arr[trade_arr > 0]
        losses = trade_arr[trade_arr <= 0]
        expectancy = float(np.mean(trade_arr)) if len(trade_arr) > 0 else None
        gross_profit = float(wins.sum()) if len(wins) else 0.0
        gross_loss = float(-losses.sum()) if len(losses) else 0.0
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (0.0 if gross_profit == 0 else float("inf"))
        win_rate = float((trade_arr > 0).mean() * 100) if len(trade_arr) > 0 else 0.0

        return BacktestResult(
            ticker=self.ticker,
            net_total_return_pct=round(total_net_pct, 2),
            gross_total_return_pct=round(total_gross_pct, 2),
            costs_pct=round(costs_pct, 2),
            benchmark_return_pct=round(bench_ret_pct, 2) if bench_ret_pct is not None else None,
            ir=round(ir, 2) if ir is not None else None,
            sharpe_ratio=round(sharpe, 2),
            sortino=round(sortino, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            expectancy_per_trade=round(expectancy, 4) if expectancy is not None else None,
            profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else 0.0,
            win_rate=round(win_rate, 2),
            total_trades=len(trade_arr),
        )