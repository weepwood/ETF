from __future__ import annotations

import pandas as pd

from etf_flow.analysis import build_event_study, build_latest_snapshot
from etf_flow.config import AppConfig


def test_event_study_uses_forward_returns_after_signal() -> None:
    dates = pd.date_range("2026-01-01", periods=6, freq="D")
    signals = pd.DataFrame(
        {
            "trade_date": dates,
            "close": [100, 99, 101, 103, 102, 105],
            "raw_signal": [False, True, False, False, False, False],
        }
    )

    result = build_event_study(signals, horizons=(1, 3))

    one_day = result.loc[result["horizon_days"] == 1].iloc[0]
    assert one_day["signal_count"] == 1
    assert abs(one_day["signal_mean_return"] - (101 / 99 - 1)) < 1e-12


def test_latest_snapshot_is_json_safe() -> None:
    signals = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2026-01-02"]),
            "close": [4000.0],
            "index_return": [-0.012],
            "flow_amount": [2_000_000_000.0],
            "flow_ratio": [0.02],
            "flow_z": [1.4],
            "breadth": [0.8],
            "coverage": [1.0],
            "raw_signal": [True],
        }
    )
    config = AppConfig(universe=("510300.SH",))

    snapshot = build_latest_snapshot(signals, {"cagr": 0.1}, {"cagr": 0.05}, config)

    assert snapshot["raw_signal"] is True
    assert snapshot["latest_trade_date"] == "2026-01-02"
    assert snapshot["flow_z"] == 1.4
