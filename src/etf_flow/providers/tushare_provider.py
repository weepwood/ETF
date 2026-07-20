from __future__ import annotations

import os
import time
from dataclasses import dataclass

import pandas as pd
import tushare as ts


@dataclass
class TushareProvider:
    token: str | None = None
    request_interval_seconds: float = 0.35

    def __post_init__(self) -> None:
        resolved = self.token or os.getenv("TUSHARE_TOKEN")
        if not resolved:
            raise RuntimeError(
                "TUSHARE_TOKEN is missing. Export the environment variable before downloading."
            )
        self._pro = ts.pro_api(resolved)

    def _call(self, api_name: str, **kwargs: str) -> pd.DataFrame:
        api = getattr(self._pro, api_name)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                frame = api(**kwargs)
                time.sleep(self.request_interval_seconds)
                if frame is None:
                    return pd.DataFrame()
                return frame
            except Exception as exc:  # provider errors vary by Tushare version
                last_error = exc
                time.sleep((attempt + 1) * 1.5)
        raise RuntimeError(f"Tushare call failed: {api_name}: {last_error}") from last_error

    def fetch_index_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self._call(
            "index_daily", ts_code=code, start_date=start_date, end_date=end_date
        )

    def fetch_fund_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self._call(
            "fund_daily", ts_code=code, start_date=start_date, end_date=end_date
        )

    def fetch_fund_share(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        # fund_share has a 2,000-row limit. Pull in calendar-year chunks.
        start_year = int(start_date[:4])
        end_year = int(end_date[:4])
        pieces: list[pd.DataFrame] = []
        for year in range(start_year, end_year + 1):
            left = max(start_date, f"{year}0101")
            right = min(end_date, f"{year}1231")
            piece = self._call(
                "fund_share", ts_code=code, start_date=left, end_date=right
            )
            if not piece.empty:
                pieces.append(piece)
        if not pieces:
            return pd.DataFrame(columns=["ts_code", "trade_date", "fd_share"])
        return pd.concat(pieces, ignore_index=True).drop_duplicates(
            subset=["ts_code", "trade_date"], keep="last"
        )

    def fetch_fund_nav(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self._call(
            "fund_nav", ts_code=code, start_date=start_date, end_date=end_date, market="E"
        )
