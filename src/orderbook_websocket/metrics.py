"""Microstructure metrics derived from a live L2 order book.

These are the workhorse signals of high-frequency and market-making research:

* **Order-book imbalance** — the normalized lean between bid and ask volume,
  in ``[-1, +1]``. Positive means more resting bid size (buy pressure).
* **Microprice** — a size-weighted fair value that sits between the bid and ask,
  pulled toward the side with *less* size (the side likely to be hit). Introduced
  by Gatheral & Oomen and popularized by Stoikov; a sharper short-horizon
  predictor than the plain mid price.
* **Weighted mid price** — the simplest imbalance-weighted mid, a useful baseline.

Every function takes an :class:`~orderbook_websocket.book.OrderBook` and returns a
plain ``float`` (or ``None`` when the book is one-sided), so they compose freely
with the rest of the library and require no network.

Part of Orderbook WebSocket by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from orderbook_websocket.book import OrderBook, Side


def imbalance(book: OrderBook, levels: int | None = 1) -> float | None:
    """Return the order-book imbalance over the top ``levels`` of each side.

    The imbalance is ``(bid_vol - ask_vol) / (bid_vol + ask_vol)``, bounded in
    ``[-1, +1]``. A value near ``+1`` means the book is dominated by bids (buy
    pressure); near ``-1`` means asks dominate (sell pressure); ``0`` is balanced.

    Args:
        book: The order book to measure.
        levels: How many top levels per side to aggregate. ``None`` uses the
            entire book. Defaults to ``1`` (top of book only).

    Returns:
        The imbalance in ``[-1, +1]``, or ``None`` if both sides are empty.
    """
    bid_vol = book.volume(Side.BID, levels)
    ask_vol = book.volume(Side.ASK, levels)
    total = bid_vol + ask_vol
    if total <= 0:
        return None
    return (bid_vol - ask_vol) / total


def weighted_mid_price(book: OrderBook) -> float | None:
    """Return the top-of-book size-weighted mid price.

    Unlike the plain mid, this leans toward the price with the larger opposing
    size. With bid size ``qb`` at ``pb`` and ask size ``qa`` at ``pa`` the value
    is ``(pb * qa + pa * qb) / (qa + qb)``.

    Returns:
        The weighted mid, or ``None`` if either side is empty.
    """
    pb, pa = book.best_bid, book.best_ask
    if pb is None or pa is None:
        return None
    qb = book.bids[pb]
    qa = book.asks[pa]
    total = qb + qa
    if total <= 0:
        return None
    return (pb * qa + pa * qb) / total


def microprice(book: OrderBook) -> float | None:
    """Return the Stoikov microprice from the top of book.

    The microprice weights the best bid and ask by the *imbalance*: with bid
    size ``qb`` and ask size ``qa`` it is ``pa * I + pb * (1 - I)`` where
    ``I = qb / (qb + qa)``. Equivalently it equals :func:`weighted_mid_price`,
    but is expressed in the imbalance form used throughout the literature and is
    a sharper short-horizon predictor of the next trade price than the mid.

    Returns:
        The microprice, or ``None`` if either side is empty.
    """
    pb, pa = book.best_bid, book.best_ask
    if pb is None or pa is None:
        return None
    qb = book.bids[pb]
    qa = book.asks[pa]
    total = qb + qa
    if total <= 0:
        return None
    i = qb / total
    return pa * i + pb * (1.0 - i)


def spread_bps(book: OrderBook) -> float | None:
    """Return the bid/ask spread in basis points of the mid price.

    Basis points (1 bp = 0.01%) make spreads comparable across instruments of
    very different price scales.

    Returns:
        The spread in bps, or ``None`` if the book is one-sided or the mid is
        non-positive.
    """
    spread = book.spread
    mid = book.mid_price
    if spread is None or mid is None or mid <= 0:
        return None
    return spread / mid * 10_000.0
