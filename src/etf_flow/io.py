from __future__ import annotations

from pathlib import Path

import pandas as pd


DATE_COLUMNS = ("trade_date", "nav_date", "ann_date", "date")


def normalize_dates(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in DATE_COLUMNS:
        if column in result.columns:
            result[column] = pd.to_datetime(result[column].astype(str), errors="coerce")
    return result


def write_table(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def read_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"required dataset does not exist: {path}")
    return normalize_dates(pd.read_parquet(path))
