# 数据获取方案

## 1. 推荐主源：Tushare Pro

MVP 使用 Tushare Pro，原因是同一套接口可以取得以下关键数据：

| 数据 | 接口 | 用途 |
|---|---|---|
| 指数日线 | `index_daily` | 计算沪深 300 等指数当日涨跌 |
| 场内基金日线 | `fund_daily` | 计算可交易 ETF 的开盘价、收盘价和交易净值 |
| 基金份额 | `fund_share` | 计算 ETF 真实净申购/净赎回 |
| 公募基金净值 | `fund_nav` | 将份额变化换算成估算资金金额 |
| ETF 基础信息 | `etf_basic` | 后续自动维护样本池 |

环境变量：

```bash
export TUSHARE_TOKEN="你的 Token"
```

Windows PowerShell：

```powershell
$env:TUSHARE_TOKEN="你的 Token"
```

执行：

```bash
etf-flow download --config configs/strategy.example.yaml
```

注意：`fund_share`、`fund_nav`、`fund_daily` 和 `index_daily` 需要相应积分或权限。项目不会绕过供应商权限。

## 2. 官方核验源：上交所、深交所和基金公司

交易所的 ETF 申购赎回清单适合用于核验当日 PCF、单位净值和公告时间，但不建议在 MVP 中直接把网页抓取作为唯一历史数据源：页面结构可能变化，历史文件格式也可能跨产品不一致。

建议将官方数据用于三件事：

1. 随机抽样核验 Tushare 的基金份额与净值；
2. 核实数据在真实交易日的公布时点；
3. 在重要异常流入日保存公告原件，形成可审计证据。

## 3. 免费备用源：AKShare

AKShare 适合补充 ETF 和指数历史行情，但它主要聚合公开网页数据。对于本策略最关键的“历史基金份额”字段，覆盖与稳定性需要逐接口验证，因此当前只建议作为行情备份，不作为资金流主源。

## 4. 手工 CSV 兜底格式

当没有 Tushare 权限时，可按以下格式准备文件。目录结构为 `data/manual/<dataset>/<code>.csv`，然后执行 `etf-flow import-csv --source data/manual` 转换为项目使用的 Parquet：

### `fund_share`

```csv
ts_code,trade_date,fd_share
510300.SH,20260105,123456.78
```

`fd_share` 单位为万份。

### `fund_nav`

```csv
ts_code,ann_date,nav_date,unit_nav
510300.SH,20260106,20260105,4.1234
```

### `fund_daily`

```csv
ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount
510300.SH,20260105,4.10,4.15,4.08,4.12,4.09,0.7335,1000000,412000
```

### `index_daily`

```csv
ts_code,trade_date,open,high,low,close,pre_close,pct_chg,vol,amount
000300.SH,20260105,3900,3940,3880,3920,3890,0.7712,100000000,200000000
```

## 5. 资金流计算口径

项目使用：

```text
净申购金额 = 当日份额变化 × 前一日单位净值
净申购率   = 当日份额变化 ÷ 前一日基金份额
```

这里使用的是 ETF 一级市场份额变化，不是行情软件根据主动买卖盘估算的“主力资金净流入”。两者不可混用。

## 6. 时间可用性

`trade_date=T` 不等于数据在 T 日收盘前可用。默认策略把 T 日信号延迟两个交易日，在 T+2 开盘执行。正式研究还应保存每个字段的 `ann_date` 或抓取时间，并比较 T+1、T+2、T+3 三种执行假设。
