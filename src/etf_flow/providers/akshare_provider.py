from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AkshareProvider:
    """Free data provider backed by AKShare, SSE and Eastmoney public endpoints.

    Historical ETF shares are available by date from the Shanghai Stock Exchange.
    For that reason the free provider deliberately supports an SSE-only ETF universe.
    """

    request_interval_seconds: float = 0.20
    max_attempts: int = 4
    _trading_dates: list[pd.Timestamp] = field(default_factory=list, init=False)
    _sse_scale_by_date: dict[str, pd.DataFrame] = field(default_factory=dict, init=False)

    def _call(self, name: str, function: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                frame = function()
                time.sleep(self.request_interval_seconds)
                return frame if frame is not None else pd.DataFrame()
            except Exception as exc:  # public websites expose varying exception types
                last_error = exc
                time.sleep((attempt + 1) * 1.5)
        raise RuntimeError(f"AKShare call failed: {name}: {last_error}") from last_error

    @staticmethod
    def _plain_code(code: str) -> str:
        return code.split(".", maxsplit=1)[0]

    @staticmethod
    def _index_symbol(code: str) -> str:
        aliases = {
            "000300.SH": "csi000300",
            "000905.SH": "csi000905",
            "000852.SH": "csi000852",
            "000016.SH": "sh000016",
            "000688.SH": "sh000688",
        }
        if code in aliases:
            return aliases[code]
        base, _, exchange = code.partition(".")
        if exchange == "SZ":
            return f"sz{base}"
        if exchange == "SH":
            return f"sh{base}"
        return code.lower()

    def fetch_index_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        frame = self._call(
            "stock_zh_index_daily_em",
            lambda: ak.stock_zh_index_daily_em(
                symbol=self._index_symbol(code),
                start_date=start_date,
                end_date=end_date,
            ),
        )
        if frame.empty:
            return pd.DataFrame(
                columns=[
                    "ts_code",
                    "trade_date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "pre_close",
                    "pct_chg",
                    "vol",
                    "amount",
                ]
            )
        frame = frame.rename(
            columns={
                "date": "trade_date",
                "volume": "vol",
            }
        )
        frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
        frame = frame.sort_values("trade_date")
        frame["pre_close"] = pd.to_numeric(frame["close"], errors="coerce").shift(1)
        frame["pct_chg"] = (
            pd.to_numeric(frame["close"], errors="coerce") / frame["pre_close"] - 1.0
        ) * 100.0
        frame["ts_code"] = code
        self._trading_dates = frame["trade_date"].dropna().tolist()
        return frame

    def fetch_fund_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        plain = self._plain_code(code)
        frame = self._call(
            "fund_etf_hist_em",
            lambda: ak.fund_etf_hist_em(
                symbol=plain,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="",
            ),
        )
        if frame.empty:
            return pd.DataFrame(
                columns=[
                    "ts_code",
                    "trade_date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "pre_close",
                    "pct_chg",
                    "vol",
                    "amount",
                ]
            )
        frame = frame.rename(
            columns={
                "日期": "trade_date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "vol",
                "成交额": "amount",
                "涨跌幅": "pct_chg",
            }
        )
        frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
        frame = frame.sort_values("trade_date")
        frame["pre_close"] = pd.to_numeric(frame["close"], errors="coerce").shift(1)
        frame["ts_code"] = code
        return frame

    def _load_sse_scale_date(self, trade_date: str) -> pd.DataFrame:
        if trade_date in self._sse_scale_by_date:
            return self._sse_scale_by_date[trade_date]
        try:
            frame = self._call(
                "fund_etf_scale_sse",
                lambda: ak.fund_etf_scale_sse(date=trade_date),
            )
        except RuntimeError as exc:
            logger.warning("Skipping SSE ETF share date %s: %s", trade_date, exc)
            frame = pd.DataFrame(columns=["基金代码", "统计日期", "基金份额"])
        if not frame.empty:
            frame = frame.rename(
                columns={
                    "基金代码": "plain_code",
                    "统计日期": "trade_date",
                    "基金份额": "fd_share",
                }
            )
            frame["plain_code"] = frame["plain_code"].astype(str).str.zfill(6)
            frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
            frame["fd_share"] = pd.to_numeric(frame["fd_share"], errors="coerce")
        self._sse_scale_by_date[trade_date] = frame
        return frame

    def fetch_fund_share(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if not code.endswith(".SH"):
            raise ValueError(
                f"AKShare free historical share mode supports SSE ETFs only: {code}"
            )
        left = pd.to_datetime(start_date)
        right = pd.to_datetime(end_date)
        trading_dates = [
            day for day in self._trading_dates if left <= pd.Timestamp(day) <= right
        ]
        if not trading_dates:
            trading_dates = list(pd.bdate_range(left, right))

        frames = [self._load_sse_scale_date(day.strftime("%Y%m%d")) for day in trading_dates]
        frames = [frame for frame in frames if not frame.empty]
        if not frames:
            return pd.DataFrame(columns=["ts_code", "trade_date", "fd_share"])

        combined = pd.concat(frames, ignore_index=True, sort=False)
        selected = combined[combined["plain_code"] == self._plain_code(code)].copy()
        selected["ts_code"] = code
        return selected[["ts_code", "trade_date", "fd_share"]]

    def fetch_fund_nav(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        plain = self._plain_code(code)
        frame = self._call(
            "fund_etf_fund_info_em",
            lambda: ak.fund_etf_fund_info_em(
                fund=plain,
                start_date=start_date,
                end_date=end_date,
            ),
        )
        if frame.empty:
            return pd.DataFrame(
                columns=["ts_code", "ann_date", "nav_date", "unit_nav", "accum_nav"]
            )
        frame = frame.rename(
            columns={
                "净值日期": "nav_date",
                "单位净值": "unit_nav",
                "累计净值": "accum_nav",
            }
        )
        frame["nav_date"] = pd.to_datetime(frame["nav_date"], errors="coerce")
        frame["unit_nav"] = pd.to_numeric(frame["unit_nav"], errors="coerce")
        frame["ann_date"] = frame["nav_date"]
        frame["ts_code"] = code
        return frame[["ts_code", "ann_date", "nav_date", "unit_nav", "accum_nav"]]
