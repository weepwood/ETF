# ETF Flow Backtest

A 股宽基 ETF 一级市场份额流向研究与回测工具。项目将“指数下跌时宽基 ETF 大额净申购”转化为可重复、可审计、避免明显未来函数的策略实验。

## 核心口径

本项目研究的资金流是 ETF **基金份额变化**：

```text
净申购金额 = (当日基金份额 - 前一日基金份额) × 前一日单位净值
净申购率   = (当日基金份额 - 前一日基金份额) ÷ 前一日基金份额
```

它不是行情软件根据主动买单和主动卖单推算的二级市场“主力资金流”。

## 默认策略

- 指数：沪深 300 `000300.SH`
- 交易标的：沪深 300 ETF `510300.SH`
- 信号：指数单日跌幅 ≤ -1%，且宽基 ETF 聚合净申购率 60 日 Z 分数 ≥ 1
- 数据覆盖：当天至少覆盖样本池 60%
- 执行：T 日信号，T+2 开盘买入
- 持有：5 个交易日；持仓期间出现新信号则延长
- 成本：买卖两边各 3 bps

默认延迟两个交易日，是为了避免把盘后或滞后披露的基金份额当作 T 日收盘前已知信息。

## 安装

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:TUSHARE_TOKEN="你的 Token"
```

Linux/macOS：

```bash
source .venv/bin/activate
pip install -e ".[dev]"
export TUSHARE_TOKEN="你的 Token"
```

## 运行

下载数据：

```bash
etf-flow download --config configs/strategy.example.yaml
```

没有 Tushare 权限时，可按 `docs/DATA_SOURCES.md` 的目录和字段准备 CSV，然后导入：

```bash
etf-flow import-csv --source data/manual --config configs/strategy.example.yaml
```

回测已有数据：

```bash
etf-flow backtest --config configs/strategy.example.yaml
```

下载并回测：

```bash
etf-flow run --config configs/strategy.example.yaml
```

输出：

```text
data/raw/                    原始 Parquet 数据
data/processed/              资金流、信号、交易与净值
reports/backtest.html        可视化报告
reports/metrics.json         结构化指标
```

## 数据来源

当前主数据源是 Tushare Pro：

- `index_daily`：指数日线
- `fund_daily`：场内 ETF 日线
- `fund_share`：基金份额
- `fund_nav`：基金单位净值和公告日期

交易所和基金公司公告用于抽样核验与确认真实披露时间。详细说明见 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)。

## 项目结构

```text
src/etf_flow/
├─ providers/          数据提供方
├─ pipeline.py         下载与原始数据落盘
├─ flow.py             单 ETF 与聚合资金流
├─ signals.py          逆向承接信号
├─ backtest.py         延迟执行、持仓与费用
├─ metrics.py          绩效指标
├─ report.py           HTML 报告
└─ cli.py              命令行入口
```

## 测试

```bash
ruff check src tests
pytest -q
```

## 下一阶段

- 历史时点 ETF 样本池，处理幸存者偏差；
- T+1/T+2/T+3 执行延迟和数据公告时间审计；
- “只看下跌”“只看流入”“价格+流入”的对照实验；
- 事件研究、参数热力图和滚动样本外测试；
- 上证 50、中证 500、中证 1000、创业板和科创 50 分组资金流；
- 自动生成每日信号简报，但默认不自动下单。

## 风险说明

份额流入可能来自做市、套利、指数调仓或机构置换，并不必然代表方向性看多。任何回测都可能受未来函数、幸存者偏差、数据修订和交易成本影响。本项目仅用于研究，不构成投资建议。
