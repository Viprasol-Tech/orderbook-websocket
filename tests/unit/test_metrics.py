"""Unit tests for microstructure metrics."""

from __future__ import annotations

import pytest

from orderbook_websocket import metrics
from orderbook_websocket.book import OrderBook, Side


@pytest.fixture
def book() -> OrderBook:
    """A small two-level book with a deliberate size imbalance."""
    ob = OrderBook()
    ob.apply_snapshot(
        bids={100.0: 6.0, 99.0: 4.0},
        asks={101.0: 2.0, 102.0: 8.0},
    )
    return ob


def test_imbalance_top_level(book: OrderBook) -> None:
    # bid 6 vs ask 2 -> (6-2)/(6+2) = 0.5
    assert metrics.imbalance(book, levels=1) == pytest.approx(0.5)


def test_imbalance_whole_book(book: OrderBook) -> None:
    # bids 10 vs asks 10 -> balanced
    assert metrics.imbalance(book, levels=None) == pytest.approx(0.0)


def test_imbalance_bounds_are_minus_one_to_one() -> None:
    ob = OrderBook()
    ob.apply_snapshot(bids={100.0: 5.0}, asks={101.0: 0.0001})
    value = metrics.imbalance(ob)
    assert value is not None
    assert -1.0 <= value <= 1.0


def test_imbalance_all_bids_is_plus_one() -> None:
    ob = OrderBook()
    ob.apply_delta(Side.BID, price=100.0, size=3.0)
    assert metrics.imbalance(ob) == pytest.approx(1.0)


def test_imbalance_empty_book_is_none() -> None:
    assert metrics.imbalance(OrderBook()) is None


def test_microprice_lies_between_bid_and_ask(book: OrderBook) -> None:
    mp = metrics.microprice(book)
    assert mp is not None
    assert book.best_bid is not None and book.best_ask is not None
    assert book.best_bid < mp < book.best_ask


def test_microprice_leans_toward_thin_side(book: OrderBook) -> None:
    # More size on the bid -> microprice pulled up toward the ask.
    mp = metrics.microprice(book)
    assert mp is not None
    assert mp > book.mid_price  # type: ignore[operator]


def test_microprice_equals_weighted_mid(book: OrderBook) -> None:
    assert metrics.microprice(book) == pytest.approx(metrics.weighted_mid_price(book))


def test_microprice_equals_mid_when_sizes_equal() -> None:
    ob = OrderBook()
    ob.apply_snapshot(bids={100.0: 5.0}, asks={102.0: 5.0})
    assert metrics.microprice(ob) == pytest.approx(101.0)


def test_microprice_one_sided_is_none() -> None:
    ob = OrderBook()
    ob.apply_delta(Side.BID, price=100.0, size=1.0)
    assert metrics.microprice(ob) is None
    assert metrics.weighted_mid_price(ob) is None


def test_spread_bps(book: OrderBook) -> None:
    # spread 1.0, mid 100.5 -> 1/100.5 * 10000 ~ 99.5 bps
    assert metrics.spread_bps(book) == pytest.approx(99.5024, rel=1e-3)


def test_spread_bps_one_sided_is_none() -> None:
    ob = OrderBook()
    ob.apply_delta(Side.ASK, price=101.0, size=1.0)
    assert metrics.spread_bps(ob) is None
