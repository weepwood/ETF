from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .config import AppConfig

DEFAULT_HORIZONS = (1, 3, 5, 10, 20)


def build_event_study(
    signals: pd.DataFrame,
    horizons: Iterable[int] = DEFAULT_HORIZONS,
) -> pd.DataFrame:
    """Compare forward index returns after ETF-flow signals with all trading days."""
    required = {"trade_date", "close", "raw_signal"}
    missing = required - set(signals.columns)
    if missing:
        raise ValueError(f"signal dataset missing columns: {sorted(missing)}")

    frame = signals.copy().sort_values("trade_date").reset_index(drop=True)
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    rows: list[dict[str, float | int]] = []

    for raw_horizon in horizons:
        horizon = int(raw_horizon)
        if horizon <= 0:
            raise ValueError("event-study horizons must be positive integers")

        forward = frame["close"].shift(-horizon) / frame["close"] - 1.0
        complete = forward.notna()
        signal_returns = forward[frame["raw_signal"].astype(bool) & complete].dropna()
        all_returns = forward[complete].dropna()

        signal_mean = float(signal_returns.mean()) if not signal_returns.empty else np.nan
        all_mean = float(all_returns.mean()) if not all_returns.empty else np.nan
        rows.append(
            {
                "horizon_days": horizon,
                "signal_count": int(signal_returns.size),
                "signal_mean_return": signal_mean,
                "signal_median_return": (
                    float(signal_returns.median()) if not signal_returns.empty else np.nan
                ),
                "signal_win_rate": (
                    float((signal_returns > 0).mean()) if not signal_returns.empty else np.nan
                ),
                "all_days_mean_return": all_mean,
                "excess_return": (
                    signal_mean - all_mean
                    if not np.isnan(signal_mean) and not np.isnan(all_mean)
                    else np.nan
                ),
            }
        )

    return pd.DataFrame(rows)


def build_latest_snapshot(
    signals: pd.DataFrame,
    strategy_metrics: dict[str, float],
    benchmark_metrics: dict[str, float],
    config: AppConfig,
) -> dict[str, Any]:
    if signals.empty:
        raise ValueError("cannot build a latest snapshot from an empty signal dataset")

    frame = signals.sort_values("trade_date").reset_index(drop=True)
    latest = frame.iloc[-1]
    latest_signal_rows = frame[frame["raw_signal"].astype(bool)]
    latest_signal_date = (
        latest_signal_rows.iloc[-1]["trade_date"] if not latest_signal_rows.empty else None
    )
    triggered = bool(latest.get("raw_signal", False))

    if triggered:
        status = "已触发逆向承接信号"
        interpretation = "指数下跌且宽基 ETF 净申购强度达到阈值。"
    else:
        status = "当前未触发信号"
        interpretation = "指数跌幅、ETF 净申购强度或数据覆盖率至少有一项未达到阈值。"

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "latest_trade_date": _iso_date(latest.get("trade_date")),
        "latest_signal_date": _iso_date(latest_signal_date),
        "status": status,
        "interpretation": interpretation,
        "raw_signal": triggered,
        "index_code": config.index_code,
        "trade_etf_code": config.trade_etf_code,
        "index_close": _number(latest.get("close")),
        "index_return": _number(latest.get("index_return")),
        "flow_amount": _number(latest.get("flow_amount")),
        "flow_ratio": _number(latest.get("flow_ratio")),
        "flow_z": _number(latest.get("flow_z")),
        "breadth": _number(latest.get("breadth")),
        "coverage": _number(latest.get("coverage")),
        "strategy": _clean_mapping(strategy_metrics),
        "buy_hold": _clean_mapping(benchmark_metrics),
        "rules": {
            "index_drop_threshold": config.signal.index_drop_threshold,
            "flow_z_threshold": config.signal.flow_z_threshold,
            "min_coverage": config.signal.min_coverage,
            "signal_delay_days": config.execution.signal_delay_days,
            "hold_days": config.execution.hold_days,
            "fee_bps_each_side": config.execution.fee_bps_each_side,
        },
        "config": {
            "provider": config.provider,
            "start_date": config.start_date,
            "end_date": config.resolved_end_date,
            "universe": list(config.universe),
            "signal": asdict(config.signal),
            "execution": asdict(config.execution),
        },
    }


def build_recent_signals(signals: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    columns = [
        "trade_date",
        "close",
        "index_return",
        "flow_amount",
        "flow_ratio",
        "flow_z",
        "breadth",
        "coverage",
        "raw_signal",
    ]
    available = [column for column in columns if column in signals.columns]
    frame = signals.loc[:, available].copy().sort_values("trade_date", ascending=False)
    return frame.head(max(1, int(limit))).reset_index(drop=True)


def build_signal_history(signals: pd.DataFrame, limit: int = 50) -> pd.DataFrame:
    frame = signals[signals["raw_signal"].astype(bool)].copy()
    columns = [
        "trade_date",
        "close",
        "index_return",
        "flow_amount",
        "flow_ratio",
        "flow_z",
        "breadth",
        "coverage",
    ]
    available = [column for column in columns if column in frame.columns]
    return (
        frame.loc[:, available]
        .sort_values("trade_date", ascending=False)
        .head(max(1, int(limit)))
        .reset_index(drop=True)
    )


def write_analysis_outputs(
    report_dir: Path,
    snapshot: dict[str, Any],
    event_study: pd.DataFrame,
    recent_market: pd.DataFrame,
    signal_history: pd.DataFrame,
) -> dict[str, Path]:
    import json

    report_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "snapshot": report_dir / "latest.json",
        "event_study": report_dir / "event_study.csv",
        "recent_market": report_dir / "recent_market.csv",
        "signal_history": report_dir / "signal_history.csv",
    }
    paths["snapshot"].write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    event_study.to_csv(paths["event_study"], index=False)
    recent_market.to_csv(paths["recent_market"], index=False)
    signal_history.to_csv(paths["signal_history"], index=False)
    return paths


def _clean_mapping(values: dict[str, float]) -> dict[str, float | None]:
    return {key: _number(value) for key, value in values.items()}


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _iso_date(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()
