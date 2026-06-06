"""Command-line interface for Orderbook WebSocket.

The CLI works entirely offline against a deterministic sample book so every
command is reproducible with no network or API keys:

* ``demo`` — load a snapshot, apply deltas, print the top of book.
* ``depth`` — print the sorted depth ladder with cumulative volume.
* ``metrics`` — print microprice, imbalance, weighted mid, and spread in bps.
* ``validate`` — run consistency checks and print a CRC32 checksum.
* ``export`` — write the sample book to a JSON snapshot file.
* ``version`` — print the installed version.

Part of Orderbook WebSocket by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from orderbook_websocket import __version__, metrics, snapshot, validator
from orderbook_websocket.book import OrderBook, Side

app = typer.Typer(add_completion=False, help="Orderbook WebSocket — by Viprasol Tech.")
console = Console()


def _fmt(value: float | None, places: int = 2) -> str:
    """Format an optional number for console output."""
    return "n/a" if value is None else f"{value:,.{places}f}"


def _sample_book() -> OrderBook:
    """Build the deterministic sample book used by every CLI command."""
    book = OrderBook()
    book.apply_snapshot(
        bids={100.0: 5.0, 99.5: 8.0, 99.0: 12.0},
        asks={100.5: 4.0, 101.0: 9.0, 101.5: 15.0},
    )
    return book


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"orderbook-websocket [bold cyan]{__version__}[/] - by Viprasol Tech")


@app.command()
def demo() -> None:
    """Build a book from a snapshot, apply deltas, and print the top of book."""
    book = _sample_book()
    console.print("[bold]Snapshot loaded[/]")
    console.print(
        f"  best bid {_fmt(book.best_bid)}  |  best ask {_fmt(book.best_ask)}  "
        f"|  spread {_fmt(book.spread)}  |  mid {_fmt(book.mid_price)}"
    )

    # A new, more aggressive bid arrives and becomes the top of book.
    book.apply_delta(Side.BID, price=100.25, size=3.0)
    # The previous best ask is fully consumed -> size 0 removes the level.
    book.apply_delta(Side.ASK, price=100.5, size=0.0)
    # A fresh ask level is added deeper in the book.
    book.apply_delta(Side.ASK, price=101.25, size=6.0)

    console.print("\n[bold]After deltas[/] (new bid 100.25, ask 100.50 removed, ask 101.25 added)")
    console.print(
        f"  best bid [green]{_fmt(book.best_bid)}[/]  |  "
        f"best ask [red]{_fmt(book.best_ask)}[/]  |  "
        f"spread [bold]{_fmt(book.spread)}[/]  |  mid {_fmt(book.mid_price)}"
    )
    console.print(f"\n[dim]{book!r}[/]")


@app.command()
def depth(levels: int = typer.Option(5, help="Number of levels per side to show.")) -> None:
    """Print the sorted depth ladder with cumulative volume."""
    book = _sample_book()
    table = Table(title=f"Order book depth (top {levels})")
    table.add_column("Bid cum", justify="right", style="green")
    table.add_column("Bid size", justify="right", style="green")
    table.add_column("Bid", justify="right", style="bold green")
    table.add_column("Ask", justify="left", style="bold red")
    table.add_column("Ask size", justify="left", style="red")
    table.add_column("Ask cum", justify="left", style="red")

    bids = book.bid_depth(levels)
    asks = book.ask_depth(levels)
    for i in range(max(len(bids), len(asks))):
        b = bids[i] if i < len(bids) else None
        a = asks[i] if i < len(asks) else None
        table.add_row(
            _fmt(b.cumulative) if b else "",
            _fmt(b.size) if b else "",
            _fmt(b.price) if b else "",
            _fmt(a.price) if a else "",
            _fmt(a.size) if a else "",
            _fmt(a.cumulative) if a else "",
        )
    console.print(table)


@app.command(name="metrics")
def metrics_cmd(
    levels: int = typer.Option(1, "--levels", help="Levels per side for imbalance."),
) -> None:
    """Print microstructure metrics for the sample book."""
    book = _sample_book()
    console.print("[bold]Microstructure metrics[/]")
    console.print(f"  mid price        {_fmt(book.mid_price)}")
    console.print(f"  microprice       {_fmt(metrics.microprice(book), 4)}")
    console.print(f"  weighted mid     {_fmt(metrics.weighted_mid_price(book), 4)}")
    console.print(f"  imbalance (L{levels})    {_fmt(metrics.imbalance(book, levels), 4)}")
    console.print(f"  spread (bps)     {_fmt(metrics.spread_bps(book), 2)}")


@app.command()
def validate() -> None:
    """Run consistency checks on the sample book and print its CRC32 checksum."""
    book = _sample_book()
    result = validator.validate(book)
    checksum = validator.crc32(book)
    if result.ok:
        console.print("[bold green]Book is consistent[/]")
    else:
        console.print("[bold red]Book has problems:[/]")
        for problem in result.problems:
            console.print(f"  - {problem}")
    console.print(f"  crossed: {book.is_crossed()}")
    console.print(f"  CRC32:   [cyan]{checksum}[/]")


@app.command()
def export(
    path: str = typer.Argument("orderbook-snapshot.json", help="Output JSON path."),
) -> None:
    """Export the sample book to a JSON snapshot file."""
    book = _sample_book()
    out = snapshot.save(book, path, meta={"symbol": "DEMO-USD", "source": "cli"})
    console.print(f"Wrote snapshot to [cyan]{out}[/]")


if __name__ == "__main__":
    app()
