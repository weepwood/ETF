from __future__ import annotations

import math

import numpy as np
import pandas as pd


def summarize(equity: pd.DataFrame, trades: pd.DataFrame | None = None) -> dict[str, float]:
    series = equity.set_index("trade_date")["equity"].astype(float).dropna()
    if len(series) < 2:
        raise ValueError("at least two equity observations are required")

    daily = series.pct_change().fillna(0.0)
    years = max((series.index[-1] - series.index[0]).days / 365.25, 1 / 365.25)
    total_return = series.iloc[-1] / series.iloc[0] - 1.0
    cagr = (series.iloc[-1] / series.iloc[0]) ** (1.0 / years) - 1.0
    volatility = daily.std(ddof=0) * math.sqrt(252)
    sharpe = (daily.mean() * 252) / volatility if volatility > 0 else float("nan")
    drawdown = series / series.cummax() - 1.0
    max_drawdown = float(drawdown.min())
    calmar = cagr / abs(max_drawdown) if max_drawdown < 0 else float("nan")

    result = {
        "total_return": float(total_return),
        "cagr": float(cagr),
        "annual_volatility": float(volatility),
        "sharpe_zero_rf": float(sharpe),
        "max_drawdown": max_drawdown,
        "calmar": float(calmar),
    }
    if "position" in equity.columns:
        result["exposure"] = float(equity["position"].mean())
    if trades is not None:
        result["trades"] = float(len(trades))
        result["win_rate"] = (
            float((trades["return"] > 0).mean()) if not trades.empty else np.nan
        )
        result["average_trade_return"] = (
            float(trades["return"].mean()) if not trades.empty else np.nan
        )
    return result
