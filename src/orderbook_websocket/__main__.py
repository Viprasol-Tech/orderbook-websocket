"""Enable ``python -m orderbook_websocket`` to run the CLI.

Part of Orderbook WebSocket by Viprasol Tech Private Limited (https://viprasol.com).
"""

from __future__ import annotations

from orderbook_websocket.cli import app

if __name__ == "__main__":
    app()
