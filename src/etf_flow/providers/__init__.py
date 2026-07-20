from __future__ import annotations

from typing import Protocol

import pandas as pd


class MarketDataProvider(Protocol):
    def fetch_index_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame: ...

    def fetch_fund_daily(self, code: str, start_date: str, end_date: str) -> pd.DataFrame: ...

    def fetch_fund_share(self, code: str, start_date: str, end_date: str) -> pd.DataFrame: ...

    def fetch_fund_nav(self, code: str, start_date: str, end_date: str) -> pd.DataFrame: ...


def build_provider(name: str) -> MarketDataProvider:
    normalized = name.strip().lower()
    if normalized in {"akshare", "akshare_sse", "free"}:
        from .akshare_provider import AkshareProvider

        return AkshareProvider()
    if normalized == "tushare":
        try:
            from .tushare_provider import TushareProvider
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                'Tushare support is optional. Install it with pip install -e ".[tushare]".'
            ) from exc
        return TushareProvider()
    raise ValueError(f"unsupported provider: {name}")


__all__ = ["MarketDataProvider", "build_provider"]
