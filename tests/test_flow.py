import pandas as pd
import pytest

from etf_flow.flow import aggregate_flows, calculate_single_etf_flow
from etf_flow.signals import rolling_zscore


def test_flow_uses_share_change_and_previous_nav():
    share = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]),
            "fd_share": [100.0, 110.0, 99.0],
        }
    )
    nav = pd.DataFrame(
        {
            "nav_date": pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]),
            "unit_nav": [1.0, 1.1, 1.2],
            "ann_date": pd.to_datetime(["2026-01-03", "2026-01-06", "2026-01-07"]),
        }
    )
    result = calculate_single_etf_flow(share, nav, "510300.SH")
    assert result.iloc[1]["delta_shares"] == pytest.approx(100_000)
    assert result.iloc[1]["flow_amount"] == pytest.approx(100_000)
    assert result.iloc[2]["flow_amount"] == pytest.approx(-121_000)


def test_aggregate_flow_is_aum_weighted():
    dates = pd.to_datetime(["2026-01-02"])
    first = pd.DataFrame(
        {
            "ts_code": ["A"],
            "trade_date": dates,
            "flow_amount": [10.0],
            "prev_aum": [100.0],
        }
    )
    second = pd.DataFrame(
        {
            "ts_code": ["B"],
            "trade_date": dates,
            "flow_amount": [-10.0],
            "prev_aum": [300.0],
        }
    )
    result = aggregate_flows([first, second], universe_size=2)
    assert result.iloc[0]["flow_ratio"] == pytest.approx(0.0)
    assert result.iloc[0]["coverage"] == pytest.approx(1.0)
    assert result.iloc[0]["breadth"] == pytest.approx(0.5)


def test_rolling_zscore_does_not_use_future_values():
    series = pd.Series([1.0, 2.0, 3.0, 100.0])
    before = rolling_zscore(series, window=3, min_periods=2)
    changed = rolling_zscore(pd.Series([1.0, 2.0, 3.0, -100.0]), window=3, min_periods=2)
    assert before.iloc[2] == pytest.approx(changed.iloc[2])
