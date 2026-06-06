"""Unit tests for snapshot export / import."""

from __future__ import annotations

from pathlib import Path

import pytest

from orderbook_websocket import snapshot
from orderbook_websocket.book import OrderBook


@pytest.fixture
def book() -> OrderBook:
    """A small two-level book."""
    ob = OrderBook()
    ob.apply_snapshot(
        bids={100.0: 5.0, 99.0: 8.0},
        asks={101.0: 4.0, 102.0: 9.0},
    )
    return ob


def test_to_dict_has_version_and_sorted_levels(book: OrderBook) -> None:
    data = snapshot.to_dict(book)
    assert data["version"] == snapshot.SNAPSHOT_VERSION
    assert data["bids"] == [[100.0, 5.0], [99.0, 8.0]]
    assert data["asks"] == [[101.0, 4.0], [102.0, 9.0]]


def test_to_dict_includes_meta(book: OrderBook) -> None:
    data = snapshot.to_dict(book, meta={"symbol": "BTC-USD"})
    assert data["meta"] == {"symbol": "BTC-USD"}


def test_round_trip_dict_preserves_book(book: OrderBook) -> None:
    restored = snapshot.from_dict(snapshot.to_dict(book))
    assert restored.bids == book.bids
    assert restored.asks == book.asks


def test_round_trip_json_preserves_book(book: OrderBook) -> None:
    restored = snapshot.from_json(snapshot.to_json(book))
    assert restored.bids == book.bids
    assert restored.asks == book.asks


def test_from_dict_rejects_unknown_version(book: OrderBook) -> None:
    data = snapshot.to_dict(book)
    data["version"] = 999
    with pytest.raises(ValueError, match="unsupported snapshot version"):
        snapshot.from_dict(data)


def test_from_dict_rejects_missing_sides() -> None:
    with pytest.raises(ValueError, match="missing"):
        snapshot.from_dict({"version": snapshot.SNAPSHOT_VERSION, "bids": [[1.0, 1.0]]})


def test_save_and_load_file(book: OrderBook, tmp_path: Path) -> None:
    path = tmp_path / "snap.json"
    written = snapshot.save(book, path, meta={"source": "test"})
    assert written.exists()
    restored = snapshot.load(path)
    assert restored.bids == book.bids
    assert restored.asks == book.asks


def test_to_json_is_valid_and_indented(book: OrderBook) -> None:
    text = snapshot.to_json(book, indent=2)
    assert text.startswith("{")
    assert '"version": 1' in text


def test_empty_book_round_trips() -> None:
    restored = snapshot.from_dict(snapshot.to_dict(OrderBook()))
    assert restored.bids == {}
    assert restored.asks == {}
