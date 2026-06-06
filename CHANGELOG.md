# Changelog

All notable changes to this project are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[SemVer](https://semver.org/).

## [0.2.0] - 2025

### Added
- **Depth aggregation** — `OrderBook.depth()` / `bid_depth()` / `ask_depth()` return
  sorted `Level` rows (price, size, running cumulative volume), plus a `volume()`
  helper and an `is_crossed()` consistency check.
- **Microstructure metrics** (`orderbook_websocket.metrics`) — order-book
  `imbalance`, Stoikov `microprice`, `weighted_mid_price`, and `spread_bps`.
- **Consistency validator + checksums** (`orderbook_websocket.validator`) —
  `validate()` for crossed/locked/non-finite/non-positive detection, plus
  OKX-style `crc32()` and `verify_checksum()` for desync detection.
- **Reconnect / resubscribe strategy** (`orderbook_websocket.reconnect`) —
  `BackoffPolicy` (exponential backoff with cap + jitter) and `ReconnectStrategy`
  driving a pluggable `ConnectionLike` through connect / subscribe / resync.
- **Snapshot export / import** (`orderbook_websocket.snapshot`) — `to_dict`,
  `from_dict`, `to_json`, `from_json`, and `save` / `load` file helpers.
- **New CLI commands** — `depth`, `metrics`, `validate`, and `export`.

### Changed
- Top-level package now re-exports the new modules and types.
- Test suite expanded from 21 to 78 tests covering every new module.

## [0.1.0] - 2025

### Added
- Initial release of orderbook-websocket: Live order book client with L2 snapshot + delta application.
