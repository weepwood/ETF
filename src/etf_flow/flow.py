from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import AppConfig
from .io import read_table, write_table


REQUIRED_SHARE_COLUMNS = {"trade_date", "fd_share"}


def calculate_single_etf_flow(
    share: pd.DataFrame,
    nav: pd.DataFrame,
    code: str,
) -> pd.DataFrame:
    missing = REQUIRED_SHARE_COLUMNS - set(share.columns)
    if missing:
        raise ValueError(f"{code} fund_share missing columns: {sorted(missing)}")

    shares = share[["trade_date", "fd_share"]].copy()
    shares["fd_share"] = pd.to_numeric(shares["fd_share"], errors="coerce")
    shares = shares.dropna().sort_values("trade_date")
    shares["shares"] = shares["fd_share"] * 10_000.0

    nav_date = "nav_date" if "nav_date" in nav.columns else "trade_date"
    if nav.empty or nav_date not in nav.columns or "unit_nav" not in nav.columns:
        merged = shares.assign(unit_nav=np.nan, ann_date=pd.NaT)
    else:
        nav_columns = [nav_date, "unit_nav"]
        if "ann_date" in nav.columns:
            nav_columns.append("ann_date")
        nav_data = nav[nav_columns].copy().rename(columns={nav_date: "trade_date"})
        nav_data["unit_nav"] = pd.to_numeric(nav_data["unit_nav"], errors="coerce")
        merged = shares.merge(nav_data, on="trade_date", how="left")
        if "ann_date" not in merged.columns:
            merged["ann_date"] = pd.NaT

    merged["prev_shares"] = merged["shares"].shift(1)
    merged["prev_nav"] = merged["unit_nav"].shift(1)
    merged["delta_shares"] = merged["shares"] - merged["prev_shares"]
    merged["flow_amount"] = merged["delta_shares"] * merged["prev_nav"]
    merged["prev_aum"] = merged["prev_shares"] * merged["prev_nav"]
    merged["flow_ratio"] = merged["delta_shares"] / merged["prev_shares"]
    merged["ts_code"] = code
    return merged[
        [
            "ts_code",
            "trade_date",
            "ann_date",
            "shares",
            "delta_shares",
            "unit_nav",
            "flow_amount",
            "prev_aum",
            "flow_ratio",
        ]
    ]


def aggregate_flows(flows: list[pd.DataFrame], universe_size: int) -> pd.DataFrame:
    combined = pd.concat(flows, ignore_index=True)
    valid = combined.dropna(subset=["flow_amount", "prev_aum"]).copy()
    if valid.empty:
        raise ValueError("no valid ETF flow observations were produced")

    grouped = valid.groupby("trade_date", as_index=False).agg(
        flow_amount=("flow_amount", "sum"),
        prev_aum=("prev_aum", "sum"),
        etf_count=("ts_code", "nunique"),
        positive_count=("flow_amount", lambda s: int((s > 0).sum())),
    )
    grouped["flow_ratio"] = grouped["flow_amount"] / grouped["prev_aum"]
    grouped["coverage"] = grouped["etf_count"] / float(universe_size)
    grouped["breadth"] = grouped["positive_count"] / grouped["etf_count"]
    return grouped.sort_values("trade_date").reset_index(drop=True)


def build_flow_dataset(config: AppConfig) -> Path:
    flows: list[pd.DataFrame] = []
    for code in config.universe:
        share = read_table(config.paths.raw_dir / "fund_share" / f"{code}.parquet")
        nav = read_table(config.paths.raw_dir / "fund_nav" / f"{code}.parquet")
        flow = calculate_single_etf_flow(share, nav, code)
        flows.append(flow)
        write_table(flow, config.paths.processed_dir / "flow_by_etf" / f"{code}.parquet")

    aggregate = aggregate_flows(flows, len(config.universe))
    output = config.paths.processed_dir / "aggregate_flow.parquet"
    write_table(aggregate, output)
    return output
