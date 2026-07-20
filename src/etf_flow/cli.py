from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import load_config
from .csv_import import import_manual_csv
from .pipeline import download_all, refresh_all
from .providers import build_provider
from .runner import run_research

app = typer.Typer(help="A-share ETF flow strategy research toolkit")
console = Console()


def _show_metrics(title: str, metrics: dict[str, float]) -> None:
    table = Table(title=title)
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    for key, value in metrics.items():
        table.add_row(key, f"{value:.6f}")
    console.print(table)


def _provider(config_path: Path):
    cfg = load_config(config_path)
    try:
        provider = build_provider(cfg.provider)
    except (RuntimeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    return cfg, provider


def _show_result(result: dict[str, object]) -> None:
    _show_metrics("Strategy", result["strategy"])
    _show_metrics("Buy & hold", result["buy_hold"])
    snapshot = result["snapshot"]
    console.print(
        f"Latest: {snapshot['latest_trade_date']} | {snapshot['status']} | "
        f"flow_z={snapshot['flow_z']}"
    )
    console.print(f"Dashboard: {result['report']}")


@app.command()
def download(config: Path = typer.Option(Path("configs/strategy.example.yaml"))) -> None:
    """Download the complete configured history, replacing the raw cache."""
    cfg, provider = _provider(config)
    written = download_all(cfg, provider)
    console.print(f"Downloaded {len(written)} datasets into {cfg.paths.raw_dir}")


@app.command()
def refresh(
    config: Path = typer.Option(Path("configs/strategy.example.yaml")),
    lookback_days: int = typer.Option(21, min=1, max=365),
) -> None:
    """Incrementally refresh data, analyze it and rebuild the dashboard."""
    cfg, provider = _provider(config)
    written = refresh_all(cfg, provider, lookback_days=lookback_days)
    console.print(f"Refreshed {len(written)} datasets into {cfg.paths.raw_dir}")
    _show_result(run_research(cfg))


@app.command("import-csv")
def import_csv(
    source: Path = typer.Option(Path("data/manual")),
    config: Path = typer.Option(Path("configs/strategy.example.yaml")),
) -> None:
    """Import manually prepared CSV files into the raw Parquet layout."""
    cfg = load_config(config)
    written = import_manual_csv(cfg, source)
    console.print(f"Imported {len(written)} datasets into {cfg.paths.raw_dir}")


@app.command()
def backtest(config: Path = typer.Option(Path("configs/strategy.example.yaml"))) -> None:
    """Analyze existing data and rebuild all reports without downloading."""
    _show_result(run_research(load_config(config)))


@app.command()
def run(
    config: Path = typer.Option(Path("configs/strategy.example.yaml")),
    lookback_days: int = typer.Option(21, min=1, max=365),
) -> None:
    """Alias for refresh: update data, analyze and rebuild the dashboard."""
    cfg, provider = _provider(config)
    refresh_all(cfg, provider, lookback_days=lookback_days)
    _show_result(run_research(cfg))


if __name__ == "__main__":
    app()
