from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import AppConfig
from .io import normalize_dates, write_table
from .providers import TushareProvider


def _clean(frame: pd.DataFrame, date_column: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    frame = normalize_dates(frame)
    frame = frame.dropna(subset=[date_column]).sort_values(date_column)
    return frame.drop_duplicates(subset=[c for c in ("ts_code", date_column) if c in frame])


def download_all(config: AppConfig, provider: TushareProvider) -> list[Path]:
    raw = config.paths.raw_dir
    written: list[Path] = []

    index = _clean(
        provider.fetch_index_daily(
            config.index_code, config.start_date, config.resolved_end_date
        ),
        "trade_date",
    )
    index_path = raw / "index" / f"{config.index_code}.parquet"
    write_table(index, index_path)
    written.append(index_path)

    all_codes = tuple(dict.fromkeys((*config.universe, config.trade_etf_code)))
    for code in all_codes:
        daily = _clean(
            provider.fetch_fund_daily(code, config.start_date, config.resolved_end_date),
            "trade_date",
        )
        daily_path = raw / "fund_daily" / f"{code}.parquet"
        write_table(daily, daily_path)
        written.append(daily_path)

        share = _clean(
            provider.fetch_fund_share(code, config.start_date, config.resolved_end_date),
            "trade_date",
        )
        share_path = raw / "fund_share" / f"{code}.parquet"
        write_table(share, share_path)
        written.append(share_path)

        nav = provider.fetch_fund_nav(code, config.start_date, config.resolved_end_date)
        if not nav.empty:
            nav = normalize_dates(nav)
            nav_date = "nav_date" if "nav_date" in nav.columns else "trade_date"
            nav = _clean(nav, nav_date)
        nav_path = raw / "fund_nav" / f"{code}.parquet"
        write_table(nav, nav_path)
        written.append(nav_path)

    return written
