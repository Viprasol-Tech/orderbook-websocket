"""Unit tests for the reconnect / resubscribe strategy."""

from __future__ import annotations

import random
from collections.abc import Sequence

import pytest

from orderbook_websocket.reconnect import (
    BackoffPolicy,
    ConnectionLike,
    ReconnectStrategy,
)


class FakeConnection:
    """A scriptable ConnectionLike that can be told to fail at a given stage."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.connected = 0
        self.subscribed: list[tuple[str, ...]] = []
        self.resynced = 0

    def connect(self) -> None:
        if self.fail_on == "connect":
            raise ConnectionError("boom")
        self.connected += 1

    def subscribe(self, channels: Sequence[str]) -> None:
        if self.fail_on == "subscribe":
            raise ConnectionError("boom")
        self.subscribed.append(tuple(channels))

    def resync(self) -> None:
        if self.fail_on == "resync":
            raise ConnectionError("boom")
        self.resynced += 1


def test_fake_connection_satisfies_protocol() -> None:
    assert isinstance(FakeConnection(), ConnectionLike)


def test_backoff_is_exponential() -> None:
    policy = BackoffPolicy(base=0.5, factor=2.0, max_delay=100.0)
    assert policy.delay_for(0) == pytest.approx(0.5)
    assert policy.delay_for(1) == pytest.approx(1.0)
    assert policy.delay_for(2) == pytest.approx(2.0)
    assert policy.delay_for(3) == pytest.approx(4.0)


def test_backoff_is_capped() -> None:
    policy = BackoffPolicy(base=1.0, factor=10.0, max_delay=5.0)
    assert policy.delay_for(10) == pytest.approx(5.0)


def test_backoff_jitter_stays_within_band() -> None:
    policy = BackoffPolicy(base=1.0, factor=2.0, max_delay=100.0, jitter=0.5)
    rng = random.Random(42)
    for attempt in range(5):
        base = min(100.0, 1.0 * 2.0**attempt)
        value = policy.delay_for(attempt, rng=rng)
        assert base * 0.5 <= value <= base * 1.5


def test_backoff_rejects_bad_params() -> None:
    with pytest.raises(ValueError):
        BackoffPolicy(base=0)
    with pytest.raises(ValueError):
        BackoffPolicy(factor=0.5)
    with pytest.raises(ValueError):
        BackoffPolicy(base=10.0, max_delay=1.0)
    with pytest.raises(ValueError):
        BackoffPolicy(jitter=2.0)


def test_delay_for_negative_attempt_raises() -> None:
    with pytest.raises(ValueError):
        BackoffPolicy().delay_for(-1)


def test_successful_reconnect_runs_full_cycle() -> None:
    conn = FakeConnection()
    strat = ReconnectStrategy(channels=("book.BTC-USD",))
    assert strat.reconnect(conn) is True
    assert conn.connected == 1
    assert conn.subscribed == [("book.BTC-USD",)]
    assert conn.resynced == 1
    assert strat.attempts == 0


def test_failed_connect_records_failure_and_returns_false() -> None:
    conn = FakeConnection(fail_on="connect")
    strat = ReconnectStrategy()
    assert strat.reconnect(conn) is False
    assert strat.attempts == 1
    assert conn.subscribed == []
    assert conn.resynced == 0


def test_failed_resync_counts_as_failure() -> None:
    conn = FakeConnection(fail_on="resync")
    strat = ReconnectStrategy(channels=("c",))
    assert strat.reconnect(conn) is False
    assert conn.connected == 1
    assert strat.attempts == 1


def test_success_resets_attempt_counter() -> None:
    strat = ReconnectStrategy()
    strat.reconnect(FakeConnection(fail_on="connect"))
    strat.reconnect(FakeConnection(fail_on="connect"))
    assert strat.attempts == 2
    strat.reconnect(FakeConnection())
    assert strat.attempts == 0


def test_next_delay_grows_with_failures() -> None:
    strat = ReconnectStrategy(policy=BackoffPolicy(base=1.0, factor=2.0, max_delay=100.0))
    assert strat.next_delay() == pytest.approx(1.0)
    strat.record_failure()
    assert strat.next_delay() == pytest.approx(2.0)


def test_should_retry_respects_max_attempts() -> None:
    strat = ReconnectStrategy(max_attempts=2)
    assert strat.should_retry() is True
    strat.record_failure()
    strat.record_failure()
    assert strat.should_retry() is False


def test_should_retry_forever_when_unbounded() -> None:
    strat = ReconnectStrategy(max_attempts=None)
    for _ in range(100):
        strat.record_failure()
    assert strat.should_retry() is True


def test_subscribe_skipped_when_no_channels() -> None:
    conn = FakeConnection()
    strat = ReconnectStrategy(channels=())
    assert strat.reconnect(conn) is True
    assert conn.subscribed == []
