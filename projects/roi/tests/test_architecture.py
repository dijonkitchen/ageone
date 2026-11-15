"""Architecture and safety checks that read the package itself."""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

import roi
from roi import cli
from roi.execution import PaperBroker
from roi.ports import Broker

PACKAGE = Path(roi.__file__).parent
CORE = [
    "domain",
    "ports",
    "screening",
    "strategy",
    "execution",
    "harness",
    "pricing",
    "research",
]


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add("." * node.level + (node.module or ""))
    return names


@pytest.mark.criteria("ARCH-1")
def test_core_imports_nothing_from_adapters() -> None:
    files = [PACKAGE / f"{m}.py" for m in CORE] + sorted(
        (PACKAGE / "analysis").glob("*.py")
    )
    for path in files:
        for name in imports_of(path):
            assert "adapters" not in name, f"{path.name} imports {name}"


@pytest.mark.criteria("ARCH-2")
def test_network_is_blocked_in_tests() -> None:
    with pytest.raises(RuntimeError, match="network"):
        socket.create_connection(("example.com", 443))
    with pytest.raises(RuntimeError, match="network"):
        urllib.request.urlopen("https://example.com", timeout=1)


@pytest.mark.criteria("ARCH-3")
def test_demo_screens_and_reports(capsys: pytest.CaptureFixture[str]) -> None:
    cli.main([])
    out = capsys.readouterr().out
    assert "Screen" in out and "RISE" in out
    assert "total return" in out and "max drawdown" in out and "trades" in out


@pytest.mark.criteria("SAFE-1")
def test_only_broker_is_the_paper_broker() -> None:
    brokers = []
    for info in pkgutil.walk_packages(roi.__path__, "roi."):
        if info.name.endswith("openbb_data"):
            continue  # imports openbb lazily; checked by name below
        module = importlib.import_module(info.name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module.__name__ or getattr(obj, "_is_protocol", False):
                continue
            if hasattr(obj, "submit") or isinstance(obj, Broker):
                brokers.append(obj)
    assert brokers == [PaperBroker]
    sdks = (
        "alpaca",
        "ib_insync",
        "ibapi",
        "robin_stocks",
        "schwab",
        "tda",
        "tradier",
        "ccxt",
    )
    for path in PACKAGE.rglob("*.py"):
        for name in imports_of(path):
            assert not name.split(".")[0] in sdks, (
                f"{path.name} imports broker SDK {name}"
            )


@pytest.mark.criteria("DATA-1")
def test_core_and_adapters_load_without_openbb() -> None:
    code = (
        "import sys, roi.adapters, roi.cli, roi.research, roi.analysis;"
        "assert not any(m == 'openbb' or m.startswith('openbb.') for m in sys.modules)"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
