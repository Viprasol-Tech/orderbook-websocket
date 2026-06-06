"""Unit tests for the Typer CLI."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from orderbook_websocket import __version__
from orderbook_websocket.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_demo_command_runs() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "best bid" in result.stdout


def test_depth_command_shows_table() -> None:
    result = runner.invoke(app, ["depth", "--levels", "3"])
    assert result.exit_code == 0
    assert "depth" in result.stdout.lower()


def test_metrics_command_shows_microprice() -> None:
    result = runner.invoke(app, ["metrics"])
    assert result.exit_code == 0
    assert "microprice" in result.stdout


def test_validate_command_reports_consistent() -> None:
    result = runner.invoke(app, ["validate"])
    assert result.exit_code == 0
    assert "consistent" in result.stdout.lower()
    assert "CRC32" in result.stdout


def test_export_command_writes_file(tmp_path: Path) -> None:
    out = tmp_path / "snap.json"
    result = runner.invoke(app, ["export", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["meta"]["symbol"] == "DEMO-USD"
