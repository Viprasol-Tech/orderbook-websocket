"""Consistency validation and CRC32 checksums for an L2 order book.

Real exchange websocket feeds (Kraken, OKX, KuCoin, ...) periodically publish a
**checksum** of the top of the book so clients can detect a corrupted or
out-of-sync local book and trigger a resync. This module provides:

* :func:`validate` — structural checks (no crossed/locked book, no non-positive
  sizes, no NaNs) returning a list of human-readable problems.
* :func:`crc32` — a deterministic CRC32 over the top ``depth`` levels, matching
  the common "``price:size`` joined by ``:``" convention used by several venues.
* :func:`verify_checksum` — compare the local CRC32 against an exchange-supplied
  value and report a mismatch.

The checksum string format (configurable precision, ``price:size`` tokens for
the top *N* bids then asks, joined by ``:``) follows the de-facto pattern used by
OKX-style feeds; pass your venue's exact precision to match byte-for-byte.

Part of Orderbook WebSocket by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import math
import zlib
from dataclasses import dataclass

from orderbook_websocket.book import OrderBook, Side


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of an order-book consistency check.

    Attributes:
        ok: ``True`` when no problems were found.
        problems: Human-readable descriptions of each issue, empty when ``ok``.
    """

    ok: bool
    problems: tuple[str, ...]

    def __bool__(self) -> bool:
        """Allow ``if validate(book): ...`` to mean "is the book valid"."""
        return self.ok


def validate(book: OrderBook) -> ValidationResult:
    """Run structural consistency checks against ``book``.

    Detects the failure modes that indicate a desynced or corrupted local book:
    a crossed/locked market, non-positive resting sizes, and non-finite prices
    or sizes (NaN/inf, usually a parsing bug).

    Args:
        book: The order book to validate.

    Returns:
        A :class:`ValidationResult`; truthy when the book is consistent.
    """
    problems: list[str] = []

    bid, ask = book.best_bid, book.best_ask
    if bid is not None and ask is not None and bid >= ask:
        kind = "locked" if bid == ask else "crossed"
        problems.append(f"book is {kind}: best_bid {bid} >= best_ask {ask}")

    for side in (Side.BID, Side.ASK):
        levels = book.bids if side is Side.BID else book.asks
        for price, size in levels.items():
            if not math.isfinite(price):
                problems.append(f"{side.value} price is not finite: {price!r}")
            if not math.isfinite(size):
                problems.append(f"{side.value} size at {price} is not finite: {size!r}")
            elif size <= 0:
                problems.append(f"{side.value} size at {price} is non-positive: {size}")

    return ValidationResult(ok=not problems, problems=tuple(problems))


def _fmt(value: float, precision: int) -> str:
    """Format a price or size to ``precision`` decimals for checksum tokens."""
    return f"{value:.{precision}f}"


def crc32(book: OrderBook, depth: int = 10, precision: int = 1) -> int:
    """Return a CRC32 checksum over the top ``depth`` levels of the book.

    The checksum is computed over a string of ``price:size`` tokens — the top
    ``depth`` bids (highest first) followed by the top ``depth`` asks (lowest
    first) — joined by ``:``. This mirrors the OKX-style convention; set
    ``precision`` to your venue's tick/lot decimals to reproduce its value.

    Args:
        book: The order book to checksum.
        depth: How many levels per side to include.
        precision: Decimal places used when formatting each price and size.

    Returns:
        The unsigned 32-bit CRC32 of the encoded book.
    """
    tokens: list[str] = []
    for level in book.bid_depth(depth):
        tokens.append(_fmt(level.price, precision))
        tokens.append(_fmt(level.size, precision))
    for level in book.ask_depth(depth):
        tokens.append(_fmt(level.price, precision))
        tokens.append(_fmt(level.size, precision))
    payload = ":".join(tokens).encode("ascii")
    return zlib.crc32(payload) & 0xFFFFFFFF


def verify_checksum(
    book: OrderBook,
    expected: int,
    depth: int = 10,
    precision: int = 1,
) -> bool:
    """Return ``True`` when the book's CRC32 matches an ``expected`` value.

    Args:
        book: The local order book.
        expected: The checksum reported by the exchange feed.
        depth: Levels per side to checksum (must match the venue's spec).
        precision: Decimal places per token (must match the venue's spec).

    Returns:
        ``True`` if the local checksum equals ``expected``; ``False`` means the
        local book has drifted and should be resynced from a fresh snapshot.
    """
    return crc32(book, depth=depth, precision=precision) == (expected & 0xFFFFFFFF)
