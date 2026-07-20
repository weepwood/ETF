from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class AkshareProvider:
    """Free provider backed by AKShare, Sina and official SSE share data.

    Sina supplies index and ETF market history. Shanghai Stock Exchange supplies
    historical clearing shares by date. ETF close prices are used as a documented
    NAV proxy when estimating flow amounts; the strategy signal itself uses the
    share-change ratio and therefore does not depend on this price proxy.
    """

    request_interval_seconds: float = 0.10
    max_attempts: int = 5
    share_download_workers: int = 4
    _trading_dates: list[pd.Timestamp] = field(default_factory=list, init=False)
    _sse_scale_by_date: dict[str, pd.DataFrame] = field(default_factory=dict, init=False)
    _fund_daily_by_code: dict[str, pd.DataFrame] = field(default_factory=dict, init=False)
    _cache_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def _call(self, name: str, function: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                frame = function()
                time.sleep(self.request_interval_seconds)
                return frame if frame is not None else pd.DataFrame()
            except Exception as exc:  # public websites expose varying exception types
                last_error = exc
                delay = min(12.0, (attempt + 1) * 2.0)
                logger.warning(
                    "AKShare call %s failed on attempt %s/%s: %s",
                    name,
                    attempt + 1,
                    self.max_attempts,
                    exc,
                )
                time.sleep(delay)
        raise RuntimeError(f"AKShare call failed: {name}: {last_error}") from last_error

    @staticmethod
    def _plain_code(code: str) -> str:
        return code.split(".", maxsplit=1)[0]

    @classmethod
    def _market_symbol(cls, code: str) -> str:
        plain = cls._plain_code(code)
        if code.endswith(".SZ"):
            return f"sz{plain}"
        return f"sh{plain}"

    @staticmethod
    def _index_symbol(code: str) -> str:
        aliases = {
            "000300.SH": "sh000300",
            "000905.SH": "sh000905",
            "000852.SH": "sh000852",
            "000016.SH": "sh000016",
            "000688.SH": "sh000688",
            "399006.SZ": "sz399006",
        }
        if code in aliases:
            return aliases[code]
        base, _, exchange = code.partition(".")
        prefix = "sz" if exchange == "SZ" else "sh"
        return f"{prefix}{base}"

    @staticmethod
    def _filter_dates(
        frame: pd.DataFrame,
        date_column: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        if frame.empty or date_column not in frame.columns:
            return frame
        frame = frame.copy()
        frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
        left = pd.to_datetime(start_date)
        right = pd.to_datetime(end_date)
        return frame[frame[date_column].between(left, right, inclusive="both")].copy()

    def fetch_index_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        frame = self._call(
            "stock_zh_index_daily",
            lambda: ak.stock_zh_index_daily(symbol=self._index_symbol(code)),
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
        frame = frame.rename(columns={"date": "trade_date", "volume": "vol"})
        frame = self._filter_dates(frame, "trade_date", start_date, end_date)
        frame = frame.sort_values("trade_date")
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame["pre_close"] = frame["close"].shift(1)
        frame["pct_chg"] = (frame["close"] / frame["pre_close"] - 1.0) * 100.0
        frame["amount"] = pd.NA
        frame["ts_code"] = code
        self._trading_dates = frame["trade_date"].dropna().tolist()
        return frame

    def fetch_fund_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        frame = self._call(
            "fund_etf_hist_sina",
            lambda: ak.fund_etf_hist_sina(symbol=self._market_symbol(code)),
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
        frame = frame.rename(columns={"date": "trade_date", "volume": "vol"})
        frame = self._filter_dates(frame, "trade_date", start_date, end_date)
        frame = frame.sort_values("trade_date")
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame["pre_close"] = frame["close"].shift(1)
        frame["pct_chg"] = (frame["close"] / frame["pre_close"] - 1.0) * 100.0
        frame["amount"] = pd.NA
        frame["ts_code"] = code
        self._fund_daily_by_code[code] = frame.copy()
        return frame

    def _load_sse_scale_date(self, trade_date: str) -> pd.DataFrame:
        with self._cache_lock:
            cached = self._sse_scale_by_date.get(trade_date)
        if cached is not None:
            return cached
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
            # The SSE scale table is expressed in ten-thousand shares. flow.py
            # converts this value into individual shares before calculations.
            frame["fd_share"] = pd.to_numeric(frame["fd_share"], errors="coerce")
        with self._cache_lock:
            self._sse_scale_by_date[trade_date] = frame
        return frame

    def _prefetch_sse_scale_dates(self, trading_dates: list[pd.Timestamp]) -> None:
        date_keys = [day.strftime("%Y%m%d") for day in trading_dates]
        with self._cache_lock:
            missing = [key for key in date_keys if key not in self._sse_scale_by_date]
        if not missing:
            return

        logger.info(
            "Downloading %s SSE ETF share dates with %s workers",
            len(missing),
            self.share_download_workers,
        )
        completed = 0
        with ThreadPoolExecutor(max_workers=max(1, self.share_download_workers)) as executor:
            futures = {executor.submit(self._load_sse_scale_date, key): key for key in missing}
            for future in as_completed(futures):
                future.result()
                completed += 1
                if completed % 100 == 0 or completed == len(missing):
                    logger.info("SSE ETF share progress: %s/%s dates", completed, len(missing))

    def fetch_fund_share(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        if not code.endswith(".SH"):
            raise ValueError(f"AKShare SSE share mode supports Shanghai ETFs only: {code}")
        left = pd.to_datetime(start_date)
        right = pd.to_datetime(end_date)
        trading_dates = [
            day for day in self._trading_dates if left <= pd.Timestamp(day) <= right
        ]
        if not trading_dates:
            trading_dates = list(pd.bdate_range(left, right))

        self._prefetch_sse_scale_dates(trading_dates)
        frames = [
            self._sse_scale_by_date[day.strftime("%Y%m%d")]
            for day in trading_dates
            if day.strftime("%Y%m%d") in self._sse_scale_by_date
        ]
        frames = [frame for frame in frames if not frame.empty]
        if not frames:
            return pd.DataFrame(columns=["ts_code", "trade_date", "fd_share"])

        combined = pd.concat(frames, ignore_index=True, sort=False)
        selected = combined[combined["plain_code"] == self._plain_code(code)].copy()
        selected["ts_code"] = code
        return selected[["ts_code", "trade_date", "fd_share"]]

    def fetch_fund_nav(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        # Free public NAV endpoints may share the same cloud-IP restrictions as
        # Eastmoney. The previous market close is an auditable proxy for the
        # monetary flow display; flow_ratio and trade signals remain share-based.
        daily = self._fund_daily_by_code.get(code)
        if daily is None:
            daily = self.fetch_fund_daily(code, start_date, end_date)
        if daily.empty:
            return pd.DataFrame(
                columns=["ts_code", "ann_date", "nav_date", "unit_nav", "accum_nav"]
            )
        frame = daily[["trade_date", "close"]].copy()
        frame = self._filter_dates(frame, "trade_date", start_date, end_date)
        frame = frame.rename(columns={"trade_date": "nav_date", "close": "unit_nav"})
        frame["unit_nav"] = pd.to_numeric(frame["unit_nav"], errors="coerce")
        frame["ann_date"] = frame["nav_date"]
        frame["accum_nav"] = pd.NA
        frame["ts_code"] = code
        frame["nav_source"] = "market_close_proxy"
        return frame[
            ["ts_code", "ann_date", "nav_date", "unit_nav", "accum_nav", "nav_source"]
        ]
