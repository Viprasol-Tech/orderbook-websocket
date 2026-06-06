"""Unit tests for the consistency validator and CRC32 checksums."""

from __future__ import annotations

import zlib

import pytest

from orderbook_websocket import validator
from orderbook_websocket.book import OrderBook, Side


@pytest.fixture
def book() -> OrderBook:
    """A clean, consistent two-level book."""
    ob = OrderBook()
    ob.apply_snapshot(
        bids={100.0: 5.0, 99.0: 8.0},
        asks={101.0: 4.0, 102.0: 9.0},
    )
    return ob


def test_valid_book_is_ok(book: OrderBook) -> None:
    result = validator.validate(book)
    assert result.ok is True
    assert result.problems == ()
    assert bool(result) is True


def test_crossed_book_is_flagged() -> None:
    ob = OrderBook()
    ob.apply_snapshot(bids={101.0: 1.0}, asks={100.0: 1.0})
    result = validator.validate(ob)
    assert result.ok is False
    assert any("crossed" in p for p in result.problems)


def test_locked_book_is_flagged() -> None:
    ob = OrderBook()
    ob.apply_snapshot(bids={100.0: 1.0}, asks={100.0: 1.0})
    result = validator.validate(ob)
    assert any("locked" in p for p in result.problems)


def test_non_finite_price_is_flagged() -> None:
    ob = OrderBook()
    ob.apply_snapshot(bids={100.0: 1.0}, asks={101.0: 1.0})
    ob.asks[float("inf")] = 1.0
    result = validator.validate(ob)
    assert any("not finite" in p for p in result.problems)


def test_validation_result_is_falsy_when_invalid() -> None:
    ob = OrderBook()
    ob.apply_snapshot(bids={101.0: 1.0}, asks={100.0: 1.0})
    assert not validator.validate(ob)


def test_crc32_is_deterministic(book: OrderBook) -> None:
    assert validator.crc32(book) == validator.crc32(book)


def test_crc32_matches_manual_okx_style_string(book: OrderBook) -> None:
    # Top bids highest-first, then asks lowest-first, "price:size" joined by ":".
    payload = "100.0:5.0:99.0:8.0:101.0:4.0:102.0:9.0".encode("ascii")
    expected = zlib.crc32(payload) & 0xFFFFFFFF
    assert validator.crc32(book) == expected


def test_crc32_changes_when_book_changes(book: OrderBook) -> None:
    before = validator.crc32(book)
    book.apply_delta(Side.BID, price=100.0, size=6.0)
    assert validator.crc32(book) != before


def test_verify_checksum_true_for_match(book: OrderBook) -> None:
    actual = validator.crc32(book)
    assert validator.verify_checksum(book, actual) is True


def test_verify_checksum_false_for_mismatch(book: OrderBook) -> None:
    assert validator.verify_checksum(book, 12345) is False


def test_crc32_precision_affects_value(book: OrderBook) -> None:
    assert validator.crc32(book, precision=1) != validator.crc32(book, precision=4)
