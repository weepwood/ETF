from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pandas as pd

from .config import AppConfig
from .io import normalize_dates, read_table, write_table
from .providers import MarketDataProvider


def _clean(frame: pd.DataFrame, date_column: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    frame = normalize_dates(frame)
    if date_column not in frame.columns:
        return frame
    frame = frame.dropna(subset=[date_column]).sort_values(date_column)
    subset = [column for column in ("ts_code", date_column) if column in frame.columns]
    return frame.drop_duplicates(subset=subset, keep="last") if subset else frame


def _merge_existing(path: Path, incoming: pd.DataFrame, date_column: str) -> pd.DataFrame:
    if path.exists():
        existing = read_table(path)
        if not existing.empty:
            incoming = pd.concat([existing, incoming], ignore_index=True, sort=False)
    return _clean(incoming, date_column)


def _incremental_start(
    path: Path,
    date_column: str,
    configured_start: str,
    end_date: str,
    lookback_days: int,
) -> str:
    if not path.exists():
        return configured_start
    existing = read_table(path)
    if existing.empty or date_column not in existing.columns:
        return configured_start
    dates = pd.to_datetime(existing[date_column], errors="coerce").dropna()
    if dates.empty:
        return configured_start
    candidate = (dates.max() - timedelta(days=max(1, lookback_days))).strftime("%Y%m%d")
    return min(end_date, max(configured_start, candidate))


def download_all(config: AppConfig, provider: MarketDataProvider) -> list[Path]:
    """Download the complete configured history and replace local raw datasets."""
    return _download(config, provider, incremental=False, lookback_days=0)


def refresh_all(
    config: AppConfig,
    provider: MarketDataProvider,
    lookback_days: int = 21,
) -> list[Path]:
    """Refresh only recent observations while retaining the local historical cache."""
    return _download(config, provider, incremental=True, lookback_days=lookback_days)


def _download(
    config: AppConfig,
    provider: MarketDataProvider,
    incremental: bool,
    lookback_days: int,
) -> list[Path]:
    raw = config.paths.raw_dir
    written: list[Path] = []
    end_date = config.resolved_end_date

    index_path = raw / "index" / f"{config.index_code}.parquet"
    index_start = (
        _incremental_start(
            index_path, "trade_date", config.start_date, end_date, lookback_days
        )
        if incremental
        else config.start_date
    )
    index = _clean(
        provider.fetch_index_daily(config.index_code, index_start, end_date),
        "trade_date",
    )
    if incremental:
        index = _merge_existing(index_path, index, "trade_date")
    write_table(index, index_path)
    written.append(index_path)

    all_codes = tuple(dict.fromkeys((*config.universe, config.trade_etf_code)))
    for code in all_codes:
        daily_path = raw / "fund_daily" / f"{code}.parquet"
        daily_start = (
            _incremental_start(
                daily_path, "trade_date", config.start_date, end_date, lookback_days
            )
            if incremental
            else config.start_date
        )
        daily = _clean(provider.fetch_fund_daily(code, daily_start, end_date), "trade_date")
        if incremental:
            daily = _merge_existing(daily_path, daily, "trade_date")
        write_table(daily, daily_path)
        written.append(daily_path)

        share_path = raw / "fund_share" / f"{code}.parquet"
        share_start = (
            _incremental_start(
                share_path, "trade_date", config.start_date, end_date, lookback_days
            )
            if incremental
            else config.start_date
        )
        share = _clean(provider.fetch_fund_share(code, share_start, end_date), "trade_date")
        if incremental:
            share = _merge_existing(share_path, share, "trade_date")
        write_table(share, share_path)
        written.append(share_path)

        nav_path = raw / "fund_nav" / f"{code}.parquet"
        nav_date_column = "nav_date"
        nav_start = (
            _incremental_start(
                nav_path, nav_date_column, config.start_date, end_date, lookback_days
            )
            if incremental
            else config.start_date
        )
        nav = provider.fetch_fund_nav(code, nav_start, end_date)
        if not nav.empty:
            nav = normalize_dates(nav)
            nav_date_column = "nav_date" if "nav_date" in nav.columns else "trade_date"
            nav = _clean(nav, nav_date_column)
        if incremental:
            nav = _merge_existing(nav_path, nav, nav_date_column)
        write_table(nav, nav_path)
        written.append(nav_path)

    return written
