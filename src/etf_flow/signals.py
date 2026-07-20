from __future__ import annotations

import numpy as np
import pandas as pd

from .config import SignalConfig


def rolling_zscore(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    mean = series.rolling(window=window, min_periods=min_periods).mean()
    std = series.rolling(window=window, min_periods=min_periods).std(ddof=0)
    return (series - mean) / std.replace(0.0, np.nan)


def build_signal_frame(
    index_daily: pd.DataFrame,
    aggregate_flow: pd.DataFrame,
    config: SignalConfig,
) -> pd.DataFrame:
    required = {"trade_date", "close"}
    missing = required - set(index_daily.columns)
    if missing:
        raise ValueError(f"index dataset missing columns: {sorted(missing)}")

    index_data = index_daily.copy().sort_values("trade_date")
    if "pre_close" in index_data.columns:
        index_data["index_return"] = index_data["close"] / index_data["pre_close"] - 1.0
    else:
        index_data["index_return"] = index_data["close"].pct_change()

    merged = index_data.merge(aggregate_flow, on="trade_date", how="left")
    merged["flow_z"] = rolling_zscore(
        merged["flow_ratio"], config.rolling_window, config.min_periods
    )
    merged["raw_signal"] = (
        (merged["index_return"] <= config.index_drop_threshold)
        & (merged["flow_z"] >= config.flow_z_threshold)
        & (merged["coverage"] >= config.min_coverage)
    )
    merged["raw_signal"] = merged["raw_signal"].fillna(False)
    return merged.sort_values("trade_date").reset_index(drop=True)
