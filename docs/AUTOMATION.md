# 自动获取、分析与展示

项目通过 GitHub Actions 在每个 A 股交易日收盘后自动运行。计划任务使用 UTC 时间，默认在周一至周五 `13:23 UTC` 执行，即中国时间 `21:23`、日本时间 `22:23`。

## 一次性配置

### 1. 添加 Tushare Token

打开仓库：

```text
Settings → Secrets and variables → Actions → New repository secret
```

名称必须是：

```text
TUSHARE_TOKEN
```

值填写你自己的 Tushare Pro Token。Token 只会作为 Actions Secret 注入，不会写入日志、代码或网页。

### 2. 启用 GitHub Pages

打开：

```text
Settings → Pages → Build and deployment → Source → GitHub Actions
```

完成后，`Daily ETF analysis` 工作流会把 `reports/index.html` 和结构化结果部署到 GitHub Pages。

### 3. 第一次手动运行

打开：

```text
Actions → Daily ETF analysis → Run workflow
```

首次运行会从配置的 `start_date` 开始下载完整历史数据，耗时和接口调用次数高于后续运行。

## 日常运行流程

```text
恢复上一轮 raw data 缓存
        ↓
回看最近 21 个自然日并增量下载
        ↓
合并、去重、覆盖数据供应商修订值
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

使用 21 日回看窗口不是重复下载全部历史数据，而是为了覆盖晚到数据、净值修订和节假日间隔。

## 自动生成的结果

| 文件 | 内容 |
|---|---|
| `reports/index.html` | 自包含数据仪表盘 |
| `reports/latest.json` | 最新交易日、信号、规则和指标快照 |
| `reports/metrics.json` | 策略与买入持有绩效 |
| `reports/event_study.csv` | 信号后 1/3/5/10/20 日收益研究 |
| `reports/recent_market.csv` | 最近 20 个交易日状态 |
| `reports/signal_history.csv` | 最近 50 次触发信号 |

GitHub Actions 还会上传 `reports/` 与 `data/processed/`，可在单次工作流页面下载。

## 缓存与失败处理

- `data/raw` 使用滚动 Actions Cache 保存，不提交到 Git 仓库，避免仓库体积持续增长。
- 如果缓存被 GitHub 清理，下一次运行会自动重新下载完整历史数据。
- 数据接口失败时工作流直接失败，不会用旧结果伪装为最新结果。
- 页面中的“最新交易日”和“生成时间”用于识别数据是否陈旧。
- `schedule` 任务可能因 GitHub Actions 负载而延迟，因此它不是精确到分钟的行情服务。

## 本地运行

```powershell
$env:TUSHARE_TOKEN="你的 Token"
etf-flow refresh --config configs/strategy.example.yaml --lookback-days 21
start reports\index.html
```

只分析已有数据：

```powershell
etf-flow backtest --config configs/strategy.example.yaml
```
