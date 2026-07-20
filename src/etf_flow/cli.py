from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import load_config
from .csv_import import import_manual_csv
from .pipeline import download_all
from .providers import TushareProvider
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


@app.command()
def download(config: Path = typer.Option(Path("configs/strategy.example.yaml"))) -> None:
    """Download index, ETF price, fund-share and NAV datasets."""
    cfg = load_config(config)
    if cfg.provider != "tushare":
        raise typer.BadParameter("the MVP currently supports provider=tushare")
    written = download_all(cfg, TushareProvider())
    console.print(f"Downloaded {len(written)} datasets into {cfg.paths.raw_dir}")


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
    """Build ETF flows, generate signals and run the backtest."""
    result = run_research(load_config(config))
    _show_metrics("Strategy", result["strategy"])
    _show_metrics("Buy & hold", result["buy_hold"])
    console.print(f"HTML report: {result['report']}")


@app.command()
def run(config: Path = typer.Option(Path("configs/strategy.example.yaml"))) -> None:
    """Download data and run the complete research pipeline."""
    cfg = load_config(config)
    if cfg.provider != "tushare":
        raise typer.BadParameter("the MVP currently supports provider=tushare")
    download_all(cfg, TushareProvider())
    result = run_research(cfg)
    _show_metrics("Strategy", result["strategy"])
    _show_metrics("Buy & hold", result["buy_hold"])
    console.print(f"HTML report: {result['report']}")


if __name__ == "__main__":
    app()
