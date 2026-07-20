from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import ExecutionConfig


@dataclass(frozen=True)
class BacktestResult:
    equity: pd.DataFrame
    trades: pd.DataFrame


def run_long_only_backtest(
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    config: ExecutionConfig,
) -> BacktestResult:
    required = {"trade_date", "open", "close"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"trade ETF dataset missing columns: {sorted(missing)}")

    price_data = prices[list(required)].copy().sort_values("trade_date")
    price_data[["open", "close"]] = price_data[["open", "close"]].apply(
        pd.to_numeric, errors="coerce"
    )
    price_data = price_data.dropna().reset_index(drop=True)

    signal_map = signals.set_index("trade_date")["raw_signal"].astype(bool)
    raw = price_data["trade_date"].map(signal_map).fillna(False).to_numpy(dtype=bool)
    executable = np.zeros(len(price_data), dtype=bool)
    delay = max(0, int(config.signal_delay_days))
    if delay == 0:
        executable[:] = raw
    elif len(raw) > delay:
        executable[delay:] = raw[:-delay]

    cash = float(config.initial_cash)
    units = 0.0
    fee_rate = float(config.fee_bps_each_side) / 10_000.0
    planned_exit: int | None = None
    entry_date: pd.Timestamp | None = None
    entry_price = 0.0
    entry_equity = 0.0
    equity_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []

    for i, row in price_data.iterrows():
        day = row["trade_date"]
        open_price = float(row["open"])
        close_price = float(row["close"])
        has_signal = bool(executable[i])

        if units > 0 and has_signal:
            planned_exit = max(planned_exit or i, i + max(1, config.hold_days))

        if units > 0 and planned_exit is not None and i >= planned_exit and not has_signal:
            proceeds = units * open_price * (1.0 - fee_rate)
            gross_value = units * open_price
            cash = proceeds
            trade_rows.append(
                {
                    "entry_date": entry_date,
                    "exit_date": day,
                    "entry_price": entry_price,
                    "exit_price": open_price,
                    "entry_equity": entry_equity,
                    "exit_equity": cash,
                    "return": cash / entry_equity - 1.0,
                    "gross_exit_value": gross_value,
                }
            )
            units = 0.0
            planned_exit = None
            entry_date = None

        if units == 0 and has_signal:
            entry_equity = cash
            entry_price = open_price
            entry_date = day
            units = cash * (1.0 - fee_rate) / open_price
            cash = 0.0
            planned_exit = i + max(1, config.hold_days)

        marked_equity = cash if units == 0 else units * close_price
        equity_rows.append(
            {
                "trade_date": day,
                "equity": marked_equity,
                "position": int(units > 0),
                "execution_signal": has_signal,
            }
        )

    if units > 0 and not price_data.empty:
        last = price_data.iloc[-1]
        cash = units * float(last["close"]) * (1.0 - fee_rate)
        trade_rows.append(
            {
                "entry_date": entry_date,
                "exit_date": last["trade_date"],
                "entry_price": entry_price,
                "exit_price": float(last["close"]),
                "entry_equity": entry_equity,
                "exit_equity": cash,
                "return": cash / entry_equity - 1.0,
                "gross_exit_value": units * float(last["close"]),
            }
        )
        equity_rows[-1]["equity"] = cash

    return BacktestResult(
        equity=pd.DataFrame(equity_rows),
        trades=pd.DataFrame(trade_rows),
    )


def build_buy_hold(prices: pd.DataFrame, initial_cash: float, fee_bps: float) -> pd.DataFrame:
    data = prices[["trade_date", "close"]].copy().sort_values("trade_date").dropna()
    fee = fee_bps / 10_000.0
    first = float(data.iloc[0]["close"])
    units = initial_cash * (1.0 - fee) / first
    data["equity"] = units * data["close"].astype(float)
    return data[["trade_date", "equity"]]
