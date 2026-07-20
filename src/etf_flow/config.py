from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SignalConfig:
    index_drop_threshold: float = -0.01
    flow_z_threshold: float = 1.0
    rolling_window: int = 60
    min_periods: int = 20
    min_coverage: float = 0.60


@dataclass(frozen=True)
class ExecutionConfig:
    signal_delay_days: int = 2
    hold_days: int = 5
    fee_bps_each_side: float = 3.0
    initial_cash: float = 1_000_000.0


@dataclass(frozen=True)
class PathConfig:
    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    report_dir: Path = Path("reports")


@dataclass(frozen=True)
class AppConfig:
    provider: str = "tushare"
    start_date: str = "20150101"
    end_date: str | None = None
    index_code: str = "000300.SH"
    trade_etf_code: str = "510300.SH"
    universe: tuple[str, ...] = field(default_factory=tuple)
    signal: SignalConfig = field(default_factory=SignalConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    paths: PathConfig = field(default_factory=PathConfig)

    @property
    def resolved_end_date(self) -> str:
        return self.end_date or date.today().strftime("%Y%m%d")


def _section(raw: dict[str, Any], name: str) -> dict[str, Any]:
    value = raw.get(name, {})
    if not isinstance(value, dict):
        raise ValueError(f"config section '{name}' must be a mapping")
    return value


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be a mapping")

    universe = tuple(str(code).upper() for code in raw.get("universe", []))
    if not universe:
        raise ValueError("universe must contain at least one ETF code")

    paths_raw = _section(raw, "paths")
    signal_raw = _section(raw, "signal")
    execution_raw = _section(raw, "execution")

    return AppConfig(
        provider=str(raw.get("provider", "tushare")),
        start_date=str(raw.get("start_date", "20150101")),
        end_date=str(raw["end_date"]) if raw.get("end_date") else None,
        index_code=str(raw.get("index_code", "000300.SH")).upper(),
        trade_etf_code=str(raw.get("trade_etf_code", "510300.SH")).upper(),
        universe=universe,
        signal=SignalConfig(**signal_raw),
        execution=ExecutionConfig(**execution_raw),
        paths=PathConfig(
            raw_dir=Path(paths_raw.get("raw_dir", "data/raw")),
            processed_dir=Path(paths_raw.get("processed_dir", "data/processed")),
            report_dir=Path(paths_raw.get("report_dir", "reports")),
        ),
    )
