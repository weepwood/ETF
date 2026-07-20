from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def _figure_data_uri(figure: plt.Figure) -> str:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    plt.close(figure)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _metrics_table(metrics: dict[str, float]) -> str:
    rows = []
    percent_keys = {
        "total_return",
        "cagr",
        "annual_volatility",
        "max_drawdown",
        "exposure",
        "win_rate",
        "average_trade_return",
    }
    for key, value in metrics.items():
        if pd.isna(value):
            rendered = "N/A"
        elif key in percent_keys:
            rendered = f"{value:.2%}"
        elif key == "trades":
            rendered = str(int(value))
        else:
            rendered = f"{value:.3f}"
        rows.append(f"<tr><td>{key}</td><td>{rendered}</td></tr>")
    return "\n".join(rows)


def generate_html_report(
    signal_frame: pd.DataFrame,
    strategy_equity: pd.DataFrame,
    benchmark_equity: pd.DataFrame,
    strategy_metrics: dict[str, float],
    benchmark_metrics: dict[str, float],
    output: Path,
) -> Path:
    merged = strategy_equity[["trade_date", "equity"]].merge(
        benchmark_equity,
        on="trade_date",
        how="inner",
        suffixes=("_strategy", "_benchmark"),
    )
    normalized = merged.copy()
    normalized["strategy"] = normalized["equity_strategy"] / normalized["equity_strategy"].iloc[0]
    normalized["buy_hold"] = normalized["equity_benchmark"] / normalized["equity_benchmark"].iloc[0]

    fig1, ax1 = plt.subplots(figsize=(11, 4.8))
    ax1.plot(normalized["trade_date"], normalized["strategy"], label="ETF flow strategy")
    ax1.plot(normalized["trade_date"], normalized["buy_hold"], label="Buy & hold")
    ax1.set_title("Normalized equity curve")
    ax1.set_ylabel("Net value")
    ax1.grid(alpha=0.25)
    ax1.legend()

    fig2, ax2 = plt.subplots(figsize=(11, 4.8))
    ax2.plot(signal_frame["trade_date"], signal_frame["flow_z"], label="Flow z-score")
    signal_points = signal_frame[signal_frame["raw_signal"]]
    ax2.scatter(signal_points["trade_date"], signal_points["flow_z"], s=18, label="Raw signal")
    ax2.axhline(0, linewidth=0.8)
    ax2.set_title("Aggregated ETF flow signal")
    ax2.grid(alpha=0.25)
    ax2.legend()

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A股 ETF 资金流战法回测</title>
<style>
body {{ max-width: 1180px; margin: 32px auto; padding: 0 20px; font-family: system-ui, sans-serif; color: #1f2937; }}
h1, h2 {{ color: #111827; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 18px; }}
.card {{ border: 1px solid #e5e7eb; border-radius: 14px; padding: 18px; background: #fff; }}
table {{ width: 100%; border-collapse: collapse; }}
td {{ border-bottom: 1px solid #eee; padding: 8px; }}
img {{ width: 100%; border-radius: 10px; }}
.note {{ background: #f3f4f6; border-radius: 10px; padding: 14px; }}
</style>
</head>
<body>
<h1>A股 ETF 资金流逆向承接策略</h1>
<p class="note">信号在 T 日形成，默认延迟两个交易日后于开盘执行，避免把盘后或滞后披露的基金份额误当作当日可用信息。报告仅用于研究，不构成投资建议。</p>
<div class="grid">
<section class="card"><h2>策略指标</h2><table>{_metrics_table(strategy_metrics)}</table></section>
<section class="card"><h2>买入持有</h2><table>{_metrics_table(benchmark_metrics)}</table></section>
</div>
<section class="card"><h2>净值曲线</h2><img src="{_figure_data_uri(fig1)}"></section>
<section class="card"><h2>资金流信号</h2><img src="{_figure_data_uri(fig2)}"></section>
</body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output
