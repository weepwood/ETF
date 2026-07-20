from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import AppConfig
from .io import normalize_dates, write_table


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    return normalize_dates(
        pd.read_csv(
            path,
            dtype={
                "ts_code": str,
                "trade_date": str,
                "nav_date": str,
                "ann_date": str,
            },
        )
    )


def import_manual_csv(config: AppConfig, source_dir: Path) -> list[Path]:
    """Import manually prepared CSV files into the canonical raw-data layout."""
    written: list[Path] = []

    index_source = source_dir / "index_daily" / f"{config.index_code}.csv"
    index_output = config.paths.raw_dir / "index" / f"{config.index_code}.parquet"
    write_table(_load_csv(index_source), index_output)
    written.append(index_output)

    all_codes = tuple(dict.fromkeys((*config.universe, config.trade_etf_code)))
    for code in all_codes:
        mappings = (
            ("fund_daily", config.paths.raw_dir / "fund_daily" / f"{code}.parquet"),
            ("fund_share", config.paths.raw_dir / "fund_share" / f"{code}.parquet"),
            ("fund_nav", config.paths.raw_dir / "fund_nav" / f"{code}.parquet"),
        )
        for dataset, output in mappings:
            source = source_dir / dataset / f"{code}.csv"
            write_table(_load_csv(source), output)
            written.append(output)
    return written
