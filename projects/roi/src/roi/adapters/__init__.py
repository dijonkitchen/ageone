"""Concrete implementations of the ports in :mod:`roi.ports`.

Adapters are the only place that should touch the outside world. v0 ships
offline adapters (`InMemoryMarketData`, `ReplayMarketData`); live vendors and
brokers are added here without changing the core.
"""

from .memory_data import InMemoryMarketData
from .openbb_data import OpenBBMarketData
from .option_quotes import InMemoryOptionQuotes
from .replay_data import ReplayMarketData
from .sec_fundamentals import (
    SECFundamentals,
    parse_company_facts,
    parse_company_facts_history,
)

__all__ = [
    "InMemoryMarketData",
    "InMemoryOptionQuotes",
    "OpenBBMarketData",
    "ReplayMarketData",
    "SECFundamentals",
    "parse_company_facts",
    "parse_company_facts_history",
]
