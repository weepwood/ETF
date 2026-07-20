# ETF Flow Backtest

A 股宽基 ETF 一级市场份额流向研究、自动分析与回测展示工具。项目将“指数下跌时宽基 ETF 大额净申购”转化为可重复、可审计、避免明显未来函数的策略实验。

## 已实现的自动化闭环

```text
Tushare 自动获取数据
        ↓
增量合并与数据质量检查
        ↓
计算 ETF 份额净申购与聚合资金流
        ↓
生成 Flow Z、交易信号和 T+2 回测
        ↓
生成事件研究与结构化结果
        ↓
GitHub Pages 展示仪表盘
```

仓库包含工作日定时任务，也支持在 Actions 页面手动触发。详细配置见 [docs/AUTOMATION.md](docs/AUTOMATION.md)。

## 核心口径

本项目研究的是 ETF **一级市场基金份额变化**：

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

## 自动分析结果

仪表盘包含：

- 最新交易日信号与规则解释
- 指数涨跌、ETF 净申购、Flow Z、流入广度和数据覆盖率
- 策略与买入持有绩效对比
- 策略净值、资金流信号与回撤图
- 信号后未来 1、3、5、10、20 日指数收益事件研究
- 最近市场状态和历史触发信号
- JSON、CSV 下载入口

输出目录：

```text
data/raw/                       原始 Parquet 数据，本地或 Actions Cache 保存
data/processed/                 资金流、信号、交易与净值
reports/index.html              可部署的自包含仪表盘
reports/latest.json             最新信号快照
reports/metrics.json            回测绩效
reports/event_study.csv         事件研究
reports/recent_market.csv       最近市场状态
reports/signal_history.csv      历史触发信号
```

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

推荐使用增量刷新命令：

```bash
etf-flow refresh --config configs/strategy.example.yaml --lookback-days 21
```

首次运行会下载完整历史数据；后续会读取 `data/raw`，仅回看最近 21 个自然日，合并供应商新增或修订的数据。

其他命令：

```bash
# 强制重新下载全部历史数据
etf-flow download --config configs/strategy.example.yaml

# 仅分析已有数据，不访问网络
etf-flow backtest --config configs/strategy.example.yaml

# refresh 的兼容别名
etf-flow run --config configs/strategy.example.yaml

# 导入手工 CSV
etf-flow import-csv --source data/manual --config configs/strategy.example.yaml
```

## 数据来源

当前主数据源是 Tushare Pro：

- `index_daily`：指数日线
- `fund_daily`：场内 ETF 日线
- `fund_share`：基金份额
- `fund_nav`：基金单位净值和公告日期

交易所和基金公司公告用于抽样核验与确认真实披露时间。详细说明见 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)。

## GitHub 自动运行

1. 在仓库 Actions Secrets 中添加 `TUSHARE_TOKEN`。
2. 在 Pages 设置中选择 `GitHub Actions` 作为发布源。
3. 合并代码后，进入 `Actions → Daily ETF analysis → Run workflow` 执行首次全量构建。
4. 此后工作流在周一至周五中国时间 21:23 自动更新。

计划任务使用 GitHub Actions Cache 保存原始数据，并将当次完整分析产物保留 30 天；它不会把大体积行情数据提交到 Git 历史。

## 项目结构

```text
src/etf_flow/
├─ providers/          数据提供方
├─ pipeline.py         全量下载、增量刷新与数据合并
├─ flow.py             单 ETF 与聚合资金流
├─ signals.py          逆向承接信号
├─ backtest.py         延迟执行、持仓与费用
├─ analysis.py         最新快照、事件研究与导出
├─ metrics.py          绩效指标
├─ report.py           静态仪表盘
├─ runner.py           完整分析流程
└─ cli.py              命令行入口
```

## 测试

```bash
ruff check src tests
pytest -q
```

## 研究边界

- 当前样本池尚未完整恢复每个历史时点真实存在的 ETF，仍有幸存者偏差风险。
- `trade_date=T` 不等于数据在 T 日收盘前可用，T+2 是保守近似，不是完整的公告时间戳审计。
- 份额流入可能来自做市、套利、指数调仓或机构置换，不必然代表方向性看多。
- GitHub 定时工作流可能延迟，不能用于盘中交易或自动下单。

本项目仅用于研究，不构成投资建议。
