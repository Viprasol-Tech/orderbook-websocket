"""Command-line interface for Orderbook WebSocket.

``orderbook-websocket demo`` builds a book from an L2 snapshot, applies a few
incremental deltas (including a level removal), and prints the top of book —
no network or API keys required.

Part of Orderbook WebSocket by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import typer
from rich.console import Console

from orderbook_websocket import __version__
from orderbook_websocket.book import OrderBook, Side

app = typer.Typer(add_completion=False, help="Orderbook WebSocket — by Viprasol Tech.")
console = Console()


def _fmt(value: float | None) -> str:
    """Format an optional price for console output."""
    return "n/a" if value is None else f"{value:,.2f}"


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"orderbook-websocket [bold cyan]{__version__}[/] - by Viprasol Tech")


@app.command()
def demo() -> None:
    """Build a book from a snapshot, apply deltas, and print the top of book."""
    book = OrderBook()
    book.apply_snapshot(
        bids={100.0: 5.0, 99.5: 8.0, 99.0: 12.0},
        asks={100.5: 4.0, 101.0: 9.0, 101.5: 15.0},
    )
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


if __name__ == "__main__":
    app()
