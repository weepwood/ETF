# ETF Flow Backtest

A 股宽基 ETF 一级市场份额流向研究、自动分析与回测展示工具。项目将“指数下跌时宽基 ETF 大额净申购”转化为可重复、可审计、尽量避免未来函数的策略实验。

## 无需付费数据

默认方案不需要 Tushare、账号、Token 或付费积分：

```text
东方财富公开接口：沪深300指数与 ETF 历史行情
天天基金公开接口：ETF 历史单位净值
上海证券交易所：按交易日查询 ETF 清算份额
        ↓
增量合并与数据质量检查
        ↓
计算 ETF 净申购、Flow Z 和流入广度
        ↓
生成交易信号、T+2 回测和事件研究
        ↓
GitHub Pages 展示仪表盘
```

数据通过 AKShare 统一访问。详细口径见 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)。

## 核心口径

```text
净申购金额 = (当日基金份额 - 前一日基金份额) × 前一日单位净值
净申购率   = (当日基金份额 - 前一日基金份额) ÷ 前一日基金份额
```

它不是行情软件根据主动买卖盘估算的二级市场“主力资金流”。

## 默认策略

- 指数：沪深 300 `000300.SH`
- 交易标的：沪深 300 ETF `510300.SH`
- 信号：指数单日跌幅 ≤ -1%，且宽基 ETF 聚合净申购率 60 日 Z 分数 ≥ 1
- 数据覆盖：当天至少覆盖样本池 60%
- 执行：T 日信号，T+2 开盘买入
- 持有：5 个交易日；持仓期间出现新信号则延长
- 成本：买卖两边各 3 bps

免费历史份额接口支持按日期查询上交所 ETF，因此默认样本池为：

```text
510050.SH  上证50 ETF
510300.SH  沪深300 ETF
510500.SH  中证500 ETF
512100.SH  中证1000 ETF
588000.SH  科创50 ETF
```

深交所免费接口目前只提供最近交易日快照，项目不会把当前份额错误填充到历史日期，所以暂不纳入创业板 ETF。

## 自动分析结果

仪表盘包含：

- 最新交易日是否触发信号及规则解释
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

## 本地安装和运行

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
etf-flow refresh --config configs/strategy.example.yaml --lookback-days 21
start reports\index.html
```

Linux/macOS：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
etf-flow refresh --config configs/strategy.example.yaml --lookback-days 21
```

首次运行从 `2020-01-01` 开始按交易日构建历史份额，时间较长；后续读取 `data/raw`，只回看最近 21 个自然日并合并新增或修订值。

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

## GitHub 自动运行

不需要添加任何 Actions Secret。

1. 合并 PR；
2. 在 `Settings → Pages` 中选择 `GitHub Actions`；
3. 进入 `Actions → Daily ETF analysis → Run workflow` 执行首次构建；
4. 此后任务在周一至周五中国时间 09:35、日本时间 10:35 自动运行。

任务安排在下一工作日上午，是为了等待上一交易日清算份额公开。GitHub Actions Cache 保存 `data/raw`，分析结果作为 Pages 和 30 天 Artifact 输出。详细说明见 [docs/AUTOMATION.md](docs/AUTOMATION.md)。

## 可选 Tushare

原 Tushare provider 仍然保留，但不是默认依赖：

```bash
pip install -e ".[tushare]"
```

将配置改为 `provider: tushare` 并设置 `TUSHARE_TOKEN` 即可。没有 Tushare 时不需要执行这些步骤。

## 项目结构

```text
src/etf_flow/
├─ providers/
│  ├─ akshare_provider.py   免费默认数据源
│  └─ tushare_provider.py   可选付费数据源
├─ pipeline.py              全量下载、增量刷新与数据合并
├─ flow.py                  单 ETF 与聚合资金流
├─ signals.py               逆向承接信号
├─ backtest.py              延迟执行、持仓与费用
├─ analysis.py              最新快照、事件研究与导出
├─ metrics.py               绩效指标
├─ report.py                静态仪表盘
├─ runner.py                完整分析流程
└─ cli.py                   命令行入口
```

## 测试

```bash
ruff check src tests
pytest -q
```

## 研究边界

- 免费数据依赖公开网页接口，页面结构或访问策略变化时需要维护；
- 当前样本池尚未完整恢复每个历史时点真实存在的全部 ETF，仍有幸存者偏差风险；
- `trade_date=T` 不等于数据在 T 日收盘前可用，T+2 是保守近似；
- 份额流入可能来自做市、套利、指数调仓或机构置换，不必然代表方向性看多；
- 定时工作流不能用于盘中交易或自动下单。

本项目仅用于研究，不构成投资建议。
