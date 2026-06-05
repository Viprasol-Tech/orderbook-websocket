"""Unit tests for the L2 order book maintainer."""

from __future__ import annotations

import pytest

from orderbook_websocket.book import OrderBook, Side


@pytest.fixture
def book() -> OrderBook:
    """A book seeded with a small three-level snapshot on each side."""
    ob = OrderBook()
    ob.apply_snapshot(
        bids={100.0: 5.0, 99.5: 8.0, 99.0: 12.0},
        asks={100.5: 4.0, 101.0: 9.0, 101.5: 15.0},
    )
    return ob


def test_snapshot_sets_levels(book: OrderBook) -> None:
    assert book.bids == {100.0: 5.0, 99.5: 8.0, 99.0: 12.0}
    assert book.asks == {100.5: 4.0, 101.0: 9.0, 101.5: 15.0}


def test_best_bid_is_highest_bid(book: OrderBook) -> None:
    assert book.best_bid == 100.0


def test_best_ask_is_lowest_ask(book: OrderBook) -> None:
    assert book.best_ask == 100.5


def test_spread_is_ask_minus_bid(book: OrderBook) -> None:
    assert book.spread == pytest.approx(0.5)


def test_mid_price_is_average(book: OrderBook) -> None:
    assert book.mid_price == pytest.approx(100.25)


def test_delta_adds_new_best_bid(book: OrderBook) -> None:
    book.apply_delta(Side.BID, price=100.25, size=3.0)
    assert book.best_bid == 100.25
    assert book.spread == pytest.approx(0.25)


def test_delta_size_zero_removes_level(book: OrderBook) -> None:
    book.apply_delta(Side.ASK, price=100.5, size=0.0)
    assert 100.5 not in book.asks
    # The next-lowest ask becomes the best ask.
    assert book.best_ask == 101.0


def test_delta_overwrites_existing_size(book: OrderBook) -> None:
    book.apply_delta(Side.BID, price=100.0, size=2.0)
    assert book.bids[100.0] == 2.0


def test_negative_size_also_removes_level(book: OrderBook) -> None:
    book.apply_delta(Side.BID, price=99.5, size=-1.0)
    assert 99.5 not in book.bids


def test_snapshot_replaces_previous_state(book: OrderBook) -> None:
    book.apply_snapshot(bids={50.0: 1.0}, asks={51.0: 1.0})
    assert book.bids == {50.0: 1.0}
    assert book.asks == {51.0: 1.0}
    assert book.best_bid == 50.0
    assert book.best_ask == 51.0


def test_snapshot_drops_zero_size_levels() -> None:
    ob = OrderBook()
    ob.apply_snapshot(bids={100.0: 5.0, 99.0: 0.0}, asks={101.0: 2.0})
    assert ob.bids == {100.0: 5.0}


def test_empty_book_has_no_top_of_book() -> None:
    ob = OrderBook()
    assert ob.best_bid is None
    assert ob.best_ask is None
    assert ob.spread is None
    assert ob.mid_price is None


def test_one_sided_book_has_no_spread() -> None:
    ob = OrderBook()
    ob.apply_delta(Side.BID, price=100.0, size=1.0)
    assert ob.best_bid == 100.0
    assert ob.best_ask is None
    assert ob.spread is None
    assert ob.mid_price is None


def test_removing_best_then_querying_next_level() -> None:
    ob = OrderBook()
    ob.apply_snapshot(bids={100.0: 1.0, 99.0: 1.0}, asks={101.0: 1.0})
    ob.apply_delta(Side.BID, price=100.0, size=0.0)
    assert ob.best_bid == 99.0
    assert ob.spread == pytest.approx(2.0)
