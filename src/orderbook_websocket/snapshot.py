"""Snapshot export / import for an L2 order book.

Persisting the book is useful for debugging desyncs, replaying a market moment,
seeding a backtest, or capturing the exact state that produced a checksum
mismatch. This module serializes an :class:`~orderbook_websocket.book.OrderBook`
to a plain JSON-friendly ``dict`` (and back), and offers file helpers.

The serialized form is stable and self-describing::

    {
      "version": 1,
      "bids": [[price, size], ...],   # highest price first
      "asks": [[price, size], ...],   # lowest price first
      "meta": { ... optional caller metadata ... }
    }

Levels are sorted on export so two equal books always produce identical output,
which keeps snapshots diff-friendly and checksum-stable.

Part of Orderbook WebSocket by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orderbook_websocket.book import OrderBook, Side

SNAPSHOT_VERSION = 1


def to_dict(book: OrderBook, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Serialize ``book`` to a JSON-friendly dictionary.

    Args:
        book: The order book to serialize.
        meta: Optional metadata (symbol, timestamp, sequence number, ...) stored
            verbatim under ``"meta"``.

    Returns:
        A dict with ``version``, sorted ``bids``/``asks`` as ``[price, size]``
        pairs, and ``meta``.
    """
    return {
        "version": SNAPSHOT_VERSION,
        "bids": [[lvl.price, lvl.size] for lvl in book.depth(Side.BID)],
        "asks": [[lvl.price, lvl.size] for lvl in book.depth(Side.ASK)],
        "meta": dict(meta) if meta else {},
    }


def from_dict(data: dict[str, Any]) -> OrderBook:
    """Reconstruct an :class:`OrderBook` from a :func:`to_dict` payload.

    Args:
        data: A dict produced by :func:`to_dict` (or matching its shape).

    Returns:
        A new order book seeded from the snapshot's levels.

    Raises:
        ValueError: If the snapshot version is unsupported or required keys are
            missing.
    """
    version = data.get("version")
    if version != SNAPSHOT_VERSION:
        raise ValueError(f"unsupported snapshot version: {version!r}")
    if "bids" not in data or "asks" not in data:
        raise ValueError("snapshot is missing 'bids' or 'asks'")
    book = OrderBook()
    book.apply_snapshot(
        bids={float(p): float(s) for p, s in data["bids"]},
        asks={float(p): float(s) for p, s in data["asks"]},
    )
    return book


def to_json(book: OrderBook, meta: dict[str, Any] | None = None, *, indent: int = 2) -> str:
    """Serialize ``book`` to a JSON string."""
    return json.dumps(to_dict(book, meta), indent=indent, sort_keys=False)


def from_json(text: str) -> OrderBook:
    """Reconstruct an :class:`OrderBook` from a JSON string."""
    return from_dict(json.loads(text))


def save(book: OrderBook, path: str | Path, meta: dict[str, Any] | None = None) -> Path:
    """Write ``book`` as JSON to ``path`` and return the resolved path.

    Args:
        book: The order book to persist.
        path: Destination file path.
        meta: Optional metadata embedded in the snapshot.

    Returns:
        The resolved :class:`~pathlib.Path` that was written.
    """
    out = Path(path)
    out.write_text(to_json(book, meta), encoding="utf-8")
    return out


def load(path: str | Path) -> OrderBook:
    """Read a JSON snapshot from ``path`` and return the reconstructed book."""
    return from_json(Path(path).read_text(encoding="utf-8"))
