"""Orderbook WebSocket — live L2 order book client by Viprasol Tech."""

from __future__ import annotations

from orderbook_websocket import metrics, snapshot, validator
from orderbook_websocket.book import Level, OrderBook, Side
from orderbook_websocket.reconnect import (
    BackoffPolicy,
    ConnectionLike,
    ReconnectStrategy,
)
from orderbook_websocket.validator import ValidationResult

__version__ = "0.2.0"
__author__ = "Viprasol Tech Private Limited"
__all__ = [
    "BackoffPolicy",
    "ConnectionLike",
    "Level",
    "OrderBook",
    "ReconnectStrategy",
    "Side",
    "ValidationResult",
    "__version__",
    "metrics",
    "snapshot",
    "validator",
]
