from __future__ import annotations

import base64
import html
import io
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


METRIC_LABELS = {
    "total_return": "累计收益",
    "cagr": "年化收益",
    "annual_volatility": "年化波动",
    "sharpe": "夏普比率",
    "max_drawdown": "最大回撤",
    "calmar": "Calmar 比率",
    "exposure": "持仓暴露",
    "trades": "交易次数",
    "win_rate": "交易胜率",
    "average_trade_return": "单笔平均收益",
}


def _figure_data_uri(figure: plt.Figure) -> str:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    plt.close(figure)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _metric_value(key: str, value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    if key in {
        "total_return",
        "cagr",
        "annual_volatility",
        "max_drawdown",
        "exposure",
        "win_rate",
        "average_trade_return",
    }:
        return f"{float(value):.2%}"
    if key == "trades":
        return str(int(value))
    return f"{float(value):.3f}"


def _metrics_table(metrics: dict[str, float]) -> str:
    rows = []
    for key, value in metrics.items():
        label = METRIC_LABELS.get(key, key)
        rows.append(
            f"<tr><td>{html.escape(label)}</td><td>{_metric_value(key, value)}</td></tr>"
        )
    return "\n".join(rows)


def _percent(value: Any, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.{digits}%}"


def _number(value: Any, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):,.{digits}f}"


def _flow_amount(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value) / 100_000_000:,.2f} 亿元"


def _event_study_table(frame: pd.DataFrame | None) -> str:
    if frame is None or frame.empty:
        return '<p class="empty">暂无足够信号样本。</p>'
    rows = []
    for _, row in frame.iterrows():
        rows.append(
            "<tr>"
            f"<td>{int(row['horizon_days'])} 日</td>"
            f"<td>{int(row['signal_count'])}</td>"
            f"<td>{_percent(row['signal_mean_return'])}</td>"
            f"<td>{_percent(row['signal_win_rate'])}</td>"
            f"<td>{_percent(row['all_days_mean_return'])}</td>"
            f"<td>{_percent(row['excess_return'])}</td>"
            "</tr>"
        )
    return (
        "<div class=\"table-wrap\"><table><thead><tr>"
        "<th>未来窗口</th><th>信号样本</th><th>信号后平均收益</th>"
        "<th>胜率</th><th>全部交易日平均</th><th>超额</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def _recent_table(frame: pd.DataFrame | None) -> str:
    if frame is None or frame.empty:
        return '<p class="empty">暂无数据。</p>'
    rows = []
    for _, row in frame.head(12).iterrows():
        signal = bool(row.get("raw_signal", False))
        badge = (
            '<span class="badge signal">触发</span>'
            if signal
            else '<span class="badge neutral">未触发</span>'
        )
        rows.append(
            "<tr>"
            f"<td>{pd.Timestamp(row['trade_date']).date().isoformat()}</td>"
            f"<td>{_percent(row.get('index_return'))}</td>"
            f"<td>{_flow_amount(row.get('flow_amount'))}</td>"
            f"<td>{_number(row.get('flow_z'))}</td>"
            f"<td>{_percent(row.get('breadth'))}</td>"
            f"<td>{_percent(row.get('coverage'))}</td>"
            f"<td>{badge}</td>"
            "</tr>"
        )
    return (
        "<div class=\"table-wrap\"><table><thead><tr>"
        "<th>交易日</th><th>指数涨跌</th><th>ETF 净申购</th><th>Flow Z</th>"
        "<th>流入广度</th><th>覆盖率</th><th>信号</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def _signal_history_table(frame: pd.DataFrame | None) -> str:
    if frame is None or frame.empty:
        return '<p class="empty">历史区间内尚未出现满足全部条件的信号。</p>'
    rows = []
    for _, row in frame.head(12).iterrows():
        rows.append(
            "<tr>"
            f"<td>{pd.Timestamp(row['trade_date']).date().isoformat()}</td>"
            f"<td>{_percent(row.get('index_return'))}</td>"
            f"<td>{_flow_amount(row.get('flow_amount'))}</td>"
            f"<td>{_number(row.get('flow_z'))}</td>"
            f"<td>{_percent(row.get('breadth'))}</td>"
            "</tr>"
        )
    return (
        "<div class=\"table-wrap\"><table><thead><tr>"
        "<th>信号日</th><th>指数涨跌</th><th>ETF 净申购</th><th>Flow Z</th><th>流入广度</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def generate_html_report(
    signal_frame: pd.DataFrame,
    strategy_equity: pd.DataFrame,
    benchmark_equity: pd.DataFrame,
    strategy_metrics: dict[str, float],
    benchmark_metrics: dict[str, float],
    output: Path,
    *,
    snapshot: dict[str, Any] | None = None,
    event_study: pd.DataFrame | None = None,
    recent_market: pd.DataFrame | None = None,
    signal_history: pd.DataFrame | None = None,
) -> Path:
    merged = strategy_equity[["trade_date", "equity"]].merge(
        benchmark_equity,
        on="trade_date",
        how="inner",
        suffixes=("_strategy", "_benchmark"),
    )
    if merged.empty:
        raise ValueError("strategy and benchmark equity curves do not overlap")
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
    signal_points = signal_frame[signal_frame["raw_signal"].astype(bool)]
    ax2.scatter(signal_points["trade_date"], signal_points["flow_z"], s=20, label="Signal")
    ax2.axhline(0, linewidth=0.8)
    ax2.set_title("Aggregated ETF flow signal")
    ax2.grid(alpha=0.25)
    ax2.legend()

    drawdown = normalized["strategy"] / normalized["strategy"].cummax() - 1.0
    fig3, ax3 = plt.subplots(figsize=(11, 3.8))
    ax3.fill_between(normalized["trade_date"], drawdown, 0, alpha=0.45)
    ax3.set_title("Strategy drawdown")
    ax3.set_ylabel("Drawdown")
    ax3.grid(alpha=0.25)

    snapshot = snapshot or {}
    status_class = "signal" if snapshot.get("raw_signal") else "neutral"
    latest_date = snapshot.get("latest_trade_date") or "N/A"
    generated_at = snapshot.get("generated_at_utc") or "N/A"
    status = html.escape(str(snapshot.get("status", "分析已完成")))
    interpretation = html.escape(str(snapshot.get("interpretation", "")))

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="A 股 ETF 资金流自动分析与回测仪表盘">
<title>A 股 ETF 资金流战法仪表盘</title>
<style>
:root {{ color-scheme: light; --bg:#f5f7fb; --card:#fff; --text:#172033; --muted:#667085; --line:#e5e9f2; --accent:#315efb; --signal:#b42318; --signal-bg:#fee4e2; --ok:#027a48; --ok-bg:#d1fadf; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:var(--bg); color:var(--text); }}
.shell {{ max-width:1280px; margin:0 auto; padding:28px 22px 56px; }}
header {{ display:flex; justify-content:space-between; gap:20px; align-items:flex-start; margin-bottom:22px; }}
h1 {{ margin:0 0 8px; font-size:clamp(28px,4vw,42px); letter-spacing:-.04em; }}
h2 {{ margin:0 0 14px; font-size:20px; }}
p {{ line-height:1.7; }}
.meta {{ color:var(--muted); font-size:13px; text-align:right; }}
.hero {{ display:grid; grid-template-columns:1.35fr .65fr; gap:18px; margin-bottom:18px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:18px; padding:20px; box-shadow:0 8px 30px rgba(30,42,70,.05); }}
.status {{ display:inline-flex; align-items:center; border-radius:999px; padding:7px 11px; font-size:13px; font-weight:700; }}
.status.signal,.badge.signal {{ color:var(--signal); background:var(--signal-bg); }}
.status.neutral,.badge.neutral {{ color:var(--ok); background:var(--ok-bg); }}
.kpis {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:18px; }}
.kpi {{ border:1px solid var(--line); border-radius:14px; padding:14px; background:#fbfcff; }}
.kpi span {{ display:block; color:var(--muted); font-size:12px; margin-bottom:7px; }}
.kpi strong {{ font-size:21px; }}
.grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; margin-bottom:18px; }}
.chart {{ margin-bottom:18px; }}
.chart img {{ width:100%; display:block; border-radius:12px; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }}
th,td {{ padding:11px 10px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }}
th:first-child,td:first-child {{ text-align:left; }}
th {{ color:var(--muted); font-size:12px; font-weight:600; background:#fafbfe; }}
.table-wrap {{ overflow:auto; border:1px solid var(--line); border-radius:12px; }}
.badge {{ display:inline-block; border-radius:999px; padding:4px 8px; font-size:12px; font-weight:700; }}
.note {{ color:var(--muted); font-size:13px; background:#f8f9fc; border-radius:12px; padding:14px; }}
.links a {{ color:var(--accent); text-decoration:none; margin-right:14px; }}
.empty {{ color:var(--muted); }}
@media (max-width:900px) {{ .hero,.grid {{ grid-template-columns:1fr; }} .kpis {{ grid-template-columns:repeat(2,1fr); }} header {{ display:block; }} .meta {{ text-align:left; margin-top:10px; }} }}
@media (max-width:520px) {{ .kpis {{ grid-template-columns:1fr; }} .shell {{ padding:20px 12px 40px; }} .card {{ padding:16px; }} }}
</style>
</head>
<body>
<div class="shell">
<header>
<div><h1>A 股 ETF 资金流战法</h1><p>自动获取 ETF 份额与净值，计算一级市场净申购，执行 T+2 回测并展示最新信号。</p></div>
<div class="meta">最新交易日：{html.escape(str(latest_date))}<br>生成时间（UTC）：{html.escape(str(generated_at))}</div>
</header>
<section class="hero">
<div class="card">
<span class="status {status_class}">{status}</span>
<h2 style="margin-top:16px">今日判断</h2>
<p>{interpretation}</p>
<div class="kpis">
<div class="kpi"><span>沪深 300 涨跌</span><strong>{_percent(snapshot.get('index_return'))}</strong></div>
<div class="kpi"><span>ETF 净申购</span><strong>{_flow_amount(snapshot.get('flow_amount'))}</strong></div>
<div class="kpi"><span>资金流 Z 分数</span><strong>{_number(snapshot.get('flow_z'))}</strong></div>
<div class="kpi"><span>样本覆盖率</span><strong>{_percent(snapshot.get('coverage'))}</strong></div>
</div>
</div>
<div class="card">
<h2>策略规则</h2>
<p class="note">指数跌幅 ≤ {_percent(snapshot.get('rules', {}).get('index_drop_threshold'))}；Flow Z ≥ {_number(snapshot.get('rules', {}).get('flow_z_threshold'))}；覆盖率 ≥ {_percent(snapshot.get('rules', {}).get('min_coverage'))}；信号延迟 {snapshot.get('rules', {}).get('signal_delay_days', 'N/A')} 个交易日执行，持有 {snapshot.get('rules', {}).get('hold_days', 'N/A')} 日。</p>
<div class="links"><a href="latest.json">最新快照 JSON</a><a href="event_study.csv">事件研究 CSV</a><a href="signal_history.csv">历史信号 CSV</a></div>
</div>
</section>
<section class="grid">
<div class="card"><h2>策略指标</h2><table>{_metrics_table(strategy_metrics)}</table></div>
<div class="card"><h2>买入持有基准</h2><table>{_metrics_table(benchmark_metrics)}</table></div>
</section>
<section class="card chart"><h2>策略净值</h2><img alt="策略与买入持有净值曲线" src="{_figure_data_uri(fig1)}"></section>
<section class="card chart"><h2>ETF 资金流信号</h2><img alt="ETF 资金流 Z 分数及信号" src="{_figure_data_uri(fig2)}"></section>
<section class="card chart"><h2>策略回撤</h2><img alt="策略回撤曲线" src="{_figure_data_uri(fig3)}"></section>
<section class="card" style="margin-bottom:18px"><h2>信号后的指数表现</h2>{_event_study_table(event_study)}</section>
<section class="card" style="margin-bottom:18px"><h2>最近市场状态</h2>{_recent_table(recent_market)}</section>
<section class="card" style="margin-bottom:18px"><h2>最近触发信号</h2>{_signal_history_table(signal_history)}</section>
<section class="note">资金流可能来自做市、套利、指数调仓或机构置换，不能直接等同于方向性看多。报告仅用于研究，不构成投资建议。</section>
</div>
</body>
</html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_text, encoding="utf-8")
    return output
