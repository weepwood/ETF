from __future__ import annotations

import json

from .backtest import build_buy_hold, run_long_only_backtest
from .config import AppConfig
from .flow import build_flow_dataset
from .io import read_table, write_table
from .metrics import summarize
from .report import generate_html_report
from .signals import build_signal_frame


def run_research(config: AppConfig) -> dict[str, object]:
    flow_path = build_flow_dataset(config)
    aggregate = read_table(flow_path)
    index_daily = read_table(config.paths.raw_dir / "index" / f"{config.index_code}.parquet")
    trade_prices = read_table(
        config.paths.raw_dir / "fund_daily" / f"{config.trade_etf_code}.parquet"
    )

    signals = build_signal_frame(index_daily, aggregate, config.signal)
    write_table(signals, config.paths.processed_dir / "signals.parquet")

    result = run_long_only_backtest(trade_prices, signals, config.execution)
    write_table(result.equity, config.paths.processed_dir / "strategy_equity.parquet")
    write_table(result.trades, config.paths.processed_dir / "trades.parquet")

    benchmark = build_buy_hold(
        trade_prices,
        config.execution.initial_cash,
        config.execution.fee_bps_each_side,
    )
    strategy_metrics = summarize(result.equity, result.trades)
    benchmark_metrics = summarize(benchmark)

    report_path = generate_html_report(
        signals,
        result.equity,
        benchmark,
        strategy_metrics,
        benchmark_metrics,
        config.paths.report_dir / "backtest.html",
    )
    metrics_path = config.paths.report_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {"strategy": strategy_metrics, "buy_hold": benchmark_metrics},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "report": report_path,
        "metrics": metrics_path,
        "strategy": strategy_metrics,
        "buy_hold": benchmark_metrics,
    }
