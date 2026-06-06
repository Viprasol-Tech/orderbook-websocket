"""L2 order book maintainer: snapshot load + incremental delta application.

This is the core logic behind a live L2 websocket market-data feed. It keeps two
price->size maps (bids and asks), applies an initial ``apply_snapshot`` and then
a stream of ``apply_delta`` updates exactly as an exchange would push them over a
websocket — a delta with ``size == 0`` removes that price level. Top-of-book
helpers (``best_bid``, ``best_ask``, ``spread``, ``mid_price``) are derived on
demand. No network is required: feed it dicts and it behaves like the real thing.

Part of Orderbook WebSocket by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import NamedTuple


class Side(str, Enum):
    """Which side of the book a price level belongs to."""

    BID = "bid"
    ASK = "ask"


class Level(NamedTuple):
    """A single aggregated price level in a depth view.

    Attributes:
        price: The price of this level.
        size: The resting size at this level.
        cumulative: Running cumulative size from the top of book down to and
            including this level — useful for sizing market orders and drawing
            depth charts.
    """

    price: float
    size: float
    cumulative: float


class OrderBook:
    """A live L2 order book maintained from a snapshot plus incremental deltas.

    Bids and asks are stored as ``{price: size}`` maps. A snapshot replaces the
    whole book; a delta updates a single level, where a ``size`` of ``0`` (or
    less) removes the level entirely — mirroring how exchanges encode removals
    on their L2 websocket channels.
    """

    def __init__(self) -> None:
        """Create an empty order book with no bids or asks."""
        self.bids: dict[float, float] = {}
        self.asks: dict[float, float] = {}

    def _book_for(self, side: Side) -> dict[float, float]:
        """Return the mutable level map for ``side``."""
        return self.bids if side is Side.BID else self.asks

    def apply_snapshot(
        self,
        bids: Mapping[float, float],
        asks: Mapping[float, float],
    ) -> None:
        """Replace the entire book with a fresh L2 snapshot.

        Any level whose size is ``0`` or negative is dropped, so a snapshot can
        be passed through untouched even if the source includes empty levels.

        Args:
            bids: Mapping of bid price to size.
            asks: Mapping of ask price to size.
        """
        self.bids = {float(p): float(s) for p, s in bids.items() if s > 0}
        self.asks = {float(p): float(s) for p, s in asks.items() if s > 0}

    def apply_delta(self, side: Side, price: float, size: float) -> None:
        """Apply a single incremental L2 update to one side of the book.

        Args:
            side: Which side (``Side.BID`` or ``Side.ASK``) to update.
            price: The price level being updated.
            size: The new total size at ``price``. A value of ``0`` (or less)
                removes the level; any positive value sets/overwrites it.
        """
        book = self._book_for(side)
        price = float(price)
        if size > 0:
            book[price] = float(size)
        else:
            book.pop(price, None)

    @property
    def best_bid(self) -> float | None:
        """Highest bid price, or ``None`` when there are no bids."""
        return max(self.bids) if self.bids else None

    @property
    def best_ask(self) -> float | None:
        """Lowest ask price, or ``None`` when there are no asks."""
        return min(self.asks) if self.asks else None

    @property
    def spread(self) -> float | None:
        """Best ask minus best bid, or ``None`` if either side is empty."""
        bid, ask = self.best_bid, self.best_ask
        if bid is None or ask is None:
            return None
        return ask - bid

    @property
    def mid_price(self) -> float | None:
        """Midpoint between best bid and best ask, or ``None`` if either is empty."""
        bid, ask = self.best_bid, self.best_ask
        if bid is None or ask is None:
            return None
        return (bid + ask) / 2.0

    def depth(self, side: Side, levels: int | None = None) -> list[Level]:
        """Return sorted price levels for ``side`` with cumulative volume.

        Bids are returned highest-price-first and asks lowest-price-first, so the
        first element is always the top of book. Each :class:`Level` carries a
        running cumulative size from the top down.

        Args:
            side: Which side of the book to return.
            levels: Maximum number of levels to return. ``None`` returns all.

        Returns:
            A list of :class:`Level` tuples sorted from best price outward.
        """
        book = self._book_for(side)
        prices = sorted(book, reverse=side is Side.BID)
        if levels is not None:
            prices = prices[:levels]
        out: list[Level] = []
        running = 0.0
        for price in prices:
            size = book[price]
            running += size
            out.append(Level(price=price, size=size, cumulative=running))
        return out

    def bid_depth(self, levels: int | None = None) -> list[Level]:
        """Return the bid side as sorted :class:`Level` rows (highest first)."""
        return self.depth(Side.BID, levels)

    def ask_depth(self, levels: int | None = None) -> list[Level]:
        """Return the ask side as sorted :class:`Level` rows (lowest first)."""
        return self.depth(Side.ASK, levels)

    def volume(self, side: Side, levels: int | None = None) -> float:
        """Return total resting size on ``side`` over the top ``levels``.

        Args:
            side: Which side to total.
            levels: How many top levels to include. ``None`` sums the whole side.
        """
        book = self._book_for(side)
        if levels is None:
            return float(sum(book.values()))
        return float(sum(level.size for level in self.depth(side, levels)))

    def is_crossed(self) -> bool:
        """Return ``True`` when the best bid is greater than or equal to the best ask.

        A crossed (or locked) book is almost always a sign of a stale snapshot,
        a missed delta, or an out-of-order update, and should trigger a resync.
        """
        bid, ask = self.best_bid, self.best_ask
        if bid is None or ask is None:
            return False
        return bid >= ask

    def __repr__(self) -> str:
        """Return a concise summary of the top of book."""
        return (
            f"OrderBook(best_bid={self.best_bid}, best_ask={self.best_ask}, "
            f"bids={len(self.bids)}, asks={len(self.asks)})"
        )
