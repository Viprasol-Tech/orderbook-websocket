"""Reconnect and resubscribe strategy for resilient websocket feeds.

Websocket market-data connections drop — for network blips, server restarts, or
rate-limit disconnects. A robust client must back off between attempts (so it
does not hammer a struggling server), eventually give up or keep trying, and on
reconnect *resubscribe* to its channels and *resync* the local book from a fresh
snapshot. This module provides the policy, not the transport:

* :class:`BackoffPolicy` — exponential backoff with optional jitter and a cap.
* :class:`ReconnectStrategy` — tracks attempt count, computes the next delay,
  and drives a pluggable :class:`ConnectionLike` through connect / resubscribe /
  resync, resetting its counter after a stable connection.

Because the delay schedule is pure and deterministic (with jitter off), it is
fully unit-testable without any real socket. Wire a real client by implementing
:class:`ConnectionLike`.

Part of Orderbook WebSocket by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class BackoffPolicy:
    """Exponential backoff schedule with an optional cap and jitter.

    The delay before attempt ``n`` (0-indexed) is
    ``min(max_delay, base * factor**n)``, optionally multiplied by a uniform
    random factor in ``[1 - jitter, 1 + jitter]``.

    Attributes:
        base: Delay in seconds before the first retry. Must be positive.
        factor: Multiplier applied per attempt. Must be >= 1.
        max_delay: Upper bound on any single delay, in seconds.
        jitter: Fractional jitter in ``[0, 1]``; ``0`` is fully deterministic.
    """

    base: float = 0.5
    factor: float = 2.0
    max_delay: float = 30.0
    jitter: float = 0.0

    def __post_init__(self) -> None:
        """Validate the policy parameters."""
        if self.base <= 0:
            raise ValueError("base must be positive")
        if self.factor < 1:
            raise ValueError("factor must be >= 1")
        if self.max_delay < self.base:
            raise ValueError("max_delay must be >= base")
        if not 0.0 <= self.jitter <= 1.0:
            raise ValueError("jitter must be in [0, 1]")

    def delay_for(self, attempt: int, rng: random.Random | None = None) -> float:
        """Return the delay in seconds before the given ``attempt`` (0-indexed).

        Args:
            attempt: Zero-based attempt number. Negative values raise.
            rng: Optional random source for jitter, for reproducible tests.

        Returns:
            The (jittered) delay in seconds, never exceeding ``max_delay``.
        """
        if attempt < 0:
            raise ValueError("attempt must be >= 0")
        raw = self.base * (self.factor**attempt)
        capped = min(self.max_delay, raw)
        if self.jitter == 0.0:
            return capped
        source = rng if rng is not None else random
        spread = self.jitter * capped
        return capped + source.uniform(-spread, spread)


@runtime_checkable
class ConnectionLike(Protocol):
    """The minimal transport surface a :class:`ReconnectStrategy` drives.

    Implement these on your real websocket client. Each call should raise on
    failure so the strategy can count the attempt and back off.
    """

    def connect(self) -> None:
        """Establish the underlying websocket connection."""

    def subscribe(self, channels: Sequence[str]) -> None:
        """Subscribe to the given market-data channels."""

    def resync(self) -> None:
        """Reload the local book from a fresh snapshot after a gap."""


@dataclass
class ReconnectStrategy:
    """Drive a connection through resilient reconnect / resubscribe / resync.

    The strategy owns the attempt counter and the channel list. After a
    successful, stable connection call :meth:`reset` (or rely on
    :meth:`reconnect` doing it) so the next outage starts its backoff afresh.

    Attributes:
        policy: The :class:`BackoffPolicy` governing delays.
        channels: Channels to resubscribe to on every (re)connect.
        max_attempts: Stop after this many consecutive failures; ``None`` retries
            forever.
    """

    policy: BackoffPolicy = field(default_factory=BackoffPolicy)
    channels: tuple[str, ...] = ()
    max_attempts: int | None = None
    _attempts: int = field(default=0, init=False, repr=False)

    @property
    def attempts(self) -> int:
        """Number of consecutive failed attempts since the last reset."""
        return self._attempts

    def reset(self) -> None:
        """Reset the failure counter after a stable connection."""
        self._attempts = 0

    def next_delay(self, rng: random.Random | None = None) -> float:
        """Return the delay before the next reconnect attempt."""
        return self.policy.delay_for(self._attempts, rng=rng)

    def should_retry(self) -> bool:
        """Return ``True`` if another attempt is allowed under ``max_attempts``."""
        if self.max_attempts is None:
            return True
        return self._attempts < self.max_attempts

    def record_failure(self) -> None:
        """Increment the consecutive-failure counter."""
        self._attempts += 1

    def reconnect(self, conn: ConnectionLike) -> bool:
        """Attempt one full reconnect cycle against ``conn``.

        Runs connect -> subscribe(channels) -> resync. On success the failure
        counter is reset and ``True`` is returned. On any exception the failure
        is recorded and ``False`` is returned; the caller is expected to sleep
        for :meth:`next_delay` before retrying (kept out of this method so the
        policy stays free of timing side effects and easy to test).

        Args:
            conn: The connection to drive.

        Returns:
            ``True`` if the cycle completed, ``False`` if it failed.
        """
        try:
            conn.connect()
            if self.channels:
                conn.subscribe(self.channels)
            conn.resync()
        except Exception:
            self.record_failure()
            return False
        self.reset()
        return True
