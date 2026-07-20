# 数据获取方案

## 1. 默认免费数据源

项目默认使用 `provider: akshare`，不需要账号、Token 或付费积分。AKShare 负责调用公开数据接口并统一为 DataFrame，实际来源如下：

| 数据 | AKShare 接口 | 实际来源 | 用途 |
|---|---|---|---|
| 指数日线 | `stock_zh_index_daily_em` | 东方财富 | 计算沪深 300 涨跌和事件研究 |
| ETF 日线 | `fund_etf_hist_em` | 东方财富 | 模拟开盘买入、收盘估值和基准收益 |
| ETF 历史份额 | `fund_etf_scale_sse` | 上海证券交易所 | 计算一级市场净申购、净赎回 |
| ETF 历史净值 | `fund_etf_fund_info_em` | 天天基金/东方财富 | 将份额变化换算为估算资金金额 |

安装项目后直接执行：

```bash
etf-flow refresh --config configs/strategy.example.yaml --lookback-days 21
```

首次运行会从配置的 `start_date` 开始逐交易日获取上交所 ETF 份额；后续使用本地或 GitHub Actions Cache，只刷新最近 21 个自然日。

## 2. 为什么默认只使用上交所 ETF

AKShare 的上交所接口允许传入日期，并返回该日期全部 ETF 的基金份额，因此可以重建历史份额序列。

深交所免费接口目前返回最近交易日快照，没有等价的历史日期参数。为了避免将当前份额错误填充到历史日期，免费样本池只保留 `.SH` ETF：

```text
510050.SH  上证50 ETF
510300.SH  沪深300 ETF
510500.SH  中证500 ETF
512100.SH  中证1000 ETF
588000.SH  科创50 ETF
```

这会损失创业板等深市 ETF 信息，但比使用不可验证的历史估算更可靠。将来若获得可靠的深交所历史份额源，可通过新的 provider 接入。

## 3. 请求次数、缓存和失败策略

上交所份额接口是“一个日期返回全部 ETF”，项目会在同一次运行中缓存日期结果，不会为每只 ETF 重复请求同一天。

- 首次从 2020 年开始构建时，需要按交易日发送较多请求；
- 后续增量刷新通常只查询最近十几个交易日；
- 公开网站请求采用串行、间隔和指数退避，不进行高并发抓取；
- 单日多次失败会跳过该日并记录警告；如果有效数据不足，分析阶段会失败，而不是把旧页面伪装成最新结果；
- `data/raw` 不提交到 Git，使用本地目录或 Actions Cache 保存。

## 4. 资金流计算口径

```text
净申购金额 = (当日基金份额 - 前一日基金份额) × 前一日单位净值
净申购率   = (当日基金份额 - 前一日基金份额) ÷ 前一日基金份额
```

上交所返回的基金份额单位为万份，程序会转换成实际份数后再计算金额。

这里研究的是 ETF 一级市场份额变化，不是行情软件根据主动买卖盘估算的二级市场“主力资金净流入”。

## 5. 时间可用性

交易所页面注明基金规模是当日清算后的统计数据。`trade_date=T` 不代表该数据在 T 日收盘前已经可用，因此：

- GitHub 定时任务安排在下一工作日上午运行；
- 回测仍将 T 日信号延迟两个交易日，在 T+2 开盘执行；
- 最新页面可能比行情日期晚一个自然日生成，这是有意的数据完整性设计。

## 6. 可选 Tushare 支持

原有 Tushare provider 保留为可选项，但默认不会安装或调用。需要时执行：

```bash
pip install -e ".[tushare]"
```

然后在配置中改为：

```yaml
provider: tushare
```

并设置 `TUSHARE_TOKEN`。免费模式不需要执行这些步骤。

## 7. 手工 CSV 兜底

仍可将授权数据放入 `data/manual/<dataset>/<code>.csv`，再执行：

```bash
etf-flow import-csv --source data/manual --config configs/strategy.example.yaml
```

基础字段：

```text
fund_share:  ts_code,trade_date,fd_share
fund_nav:    ts_code,ann_date,nav_date,unit_nav
fund_daily:  ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount
index_daily: ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount
```
