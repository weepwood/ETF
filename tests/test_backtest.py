import pandas as pd
import pytest

from etf_flow.backtest import run_long_only_backtest
from etf_flow.config import ExecutionConfig


def test_signal_is_executed_after_configured_delay():
    dates = pd.bdate_range("2026-01-01", periods=8)
    prices = pd.DataFrame(
        {
            "trade_date": dates,
            "open": [10, 10, 10, 11, 12, 13, 14, 15],
            "close": [10, 10, 10, 11, 12, 13, 14, 15],
        }
    )
    signals = pd.DataFrame(
        {"trade_date": dates, "raw_signal": [True, False, False, False, False, False, False, False]}
    )
    result = run_long_only_backtest(
        prices,
        signals,
        ExecutionConfig(
            signal_delay_days=2,
            hold_days=2,
            fee_bps_each_side=0,
            initial_cash=1000,
        ),
    )
    assert result.equity.loc[0, "position"] == 0
    assert result.equity.loc[1, "position"] == 0
    assert result.equity.loc[2, "position"] == 1
    assert result.trades.iloc[0]["entry_date"] == dates[2]
    assert result.trades.iloc[0]["exit_date"] == dates[4]
    assert result.trades.iloc[0]["return"] == pytest.approx(0.2)


def test_overlapping_signal_extends_holding_period():
    dates = pd.bdate_range("2026-01-01", periods=7)
    prices = pd.DataFrame(
        {"trade_date": dates, "open": [10] * 7, "close": [10] * 7}
    )
    signals = pd.DataFrame(
        {"trade_date": dates, "raw_signal": [True, True, False, False, False, False, False]}
    )
    result = run_long_only_backtest(
        prices,
        signals,
        ExecutionConfig(signal_delay_days=0, hold_days=2, fee_bps_each_side=0),
    )
    assert result.trades.iloc[0]["exit_date"] == dates[3]
