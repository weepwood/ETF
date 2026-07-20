# 自动获取、分析与展示

项目通过 GitHub Actions 自动获取免费公开数据、执行分析并发布静态仪表盘，不需要 Tushare Token 或其他仓库密钥。

计划任务在周一至周五 `01:35 UTC` 执行，即中国时间 `09:35`、日本时间 `10:35`。选择下一工作日上午，是为了等待上一交易日的 ETF 清算份额公开，而不是在收盘后立即使用尚未完整的数据。

## 一次性配置

### 1. 启用 GitHub Pages

打开：

```text
Settings → Pages → Build and deployment → Source → GitHub Actions
```

### 2. 合并代码并首次运行

打开：

```text
Actions → Daily ETF analysis → Run workflow
```

首次运行会从 `2020-01-01` 开始逐交易日构建上交所 ETF 历史份额，耗时明显高于后续任务。工作流最大运行时间设置为 90 分钟。

不需要创建 `TUSHARE_TOKEN` Secret。

## 日常运行流程

```text
恢复上一轮 data/raw 缓存
        ↓
从东方财富获取指数、ETF 行情和历史净值
        ↓
按日期从上交所获取 ETF 清算份额
        ↓
回看最近 21 天，合并、去重并覆盖修订值
        ↓
计算单 ETF 和聚合净申购
        ↓
生成 Flow Z、信号和 T+2 回测
        ↓
生成事件研究、最新快照和历史信号
        ↓
发布 GitHub Pages 仪表盘
        ↓
保存 30 天可下载分析产物
```

上交所单个日期的响应包含当天全部 ETF，程序在一次运行中只查询一次该日期，然后为样本池 ETF 复用结果。

## 自动生成的结果

| 文件 | 内容 |
|---|---|
| `reports/index.html` | 自包含数据仪表盘 |
| `reports/latest.json` | 最新交易日、信号、规则和指标快照 |
| `reports/metrics.json` | 策略与买入持有绩效 |
| `reports/event_study.csv` | 信号后 1/3/5/10/20 日收益研究 |
| `reports/recent_market.csv` | 最近 20 个交易日状态 |
| `reports/signal_history.csv` | 最近 50 次触发信号 |

GitHub Actions 还会上传 `reports/` 与 `data/processed/`，可以在单次工作流页面下载，保留 30 天。

## 缓存与失败处理

- `data/raw` 使用滚动 Actions Cache 保存，不提交到 Git 仓库；
- 缓存被清理后，下一次任务会重新构建完整历史数据；
- 公开接口采用低频串行请求和重试，不使用高并发；
- 接口持续失败或有效数据不足时，工作流失败，不发布伪造的“最新结果”；
- 页面中的最新交易日和生成时间用于识别数据是否陈旧；
- GitHub `schedule` 可能延迟，因此不能用于盘中交易或自动下单。

## 本地运行

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
etf-flow refresh --config configs/strategy.example.yaml --lookback-days 21
start reports\index.html
```

只分析已有数据：

```powershell
etf-flow backtest --config configs/strategy.example.yaml
```
