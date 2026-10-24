"""Local settings: the SEC contact and price provider keys (never committed), and where the databases live."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATHS = (
    PROJECT_DIR / "config.toml",
    Path.home() / ".config" / "ageone" / "stock-screener.toml",
)


@dataclass(frozen=True)
class Prices:
    """The price provider (SPEC-2026-10-03-portfolio-kelly): any OpenBB provider extension that is installed."""

    provider: str = "yfinance"
    # Keys go to OpenBB in this process and never reach the browser, e.g. {"fmp_api_key": "..."}.
    credentials: dict[str, str] = field(default_factory=dict)
    # Whether the provider's quotes are real time; most free feeds are delayed.
    realtime: bool = False
    # Seconds between quote refreshes on the page, and the shortest interval the provider's rate limit allows.
    refresh_seconds: int = 60
    min_refresh_seconds: int = 15


@dataclass(frozen=True)
class Config:
    user_agent: str | None = None
    database: Path = PROJECT_DIR / "screener.duckdb"
    requests_per_second: float = 8.0
    prices: Prices = field(default_factory=Prices)

    @property
    def prices_database(self) -> Path:
        """Daily price history and the last quotes, kept apart so the page can write it while the screener is read only."""
        return self.database.with_suffix(".prices.duckdb")

    def require_user_agent(self) -> str:
        if not self.user_agent or "@" not in self.user_agent:
            raise SystemExit(
                "The SEC asks every client to send a User-Agent with a contact email.\n"
                f"Copy config.example.toml to {CONFIG_PATHS[0]} and set user_agent, "
                "or set SEC_USER_AGENT='Your Name you@example.com'."
            )
        return self.user_agent


def load(path: Path | None = None) -> Config:
    data: dict = {}
    for candidate in ([path] if path else CONFIG_PATHS):
        if candidate and candidate.exists():
            data = tomllib.loads(candidate.read_text())
            break
    user_agent = os.environ.get("SEC_USER_AGENT") or data.get("user_agent")
    database = os.environ.get("SCREENER_DB") or data.get("database")
    rps = float(data.get("requests_per_second", 8.0))
    if not 0 < rps <= 10:
        raise SystemExit("requests_per_second must be above 0 and at most 10 (SEC fair access).")
    raw_prices = data.get("prices", {})
    prices = Prices(
        provider=raw_prices.get("provider", Prices.provider),
        credentials={k: str(v) for k, v in raw_prices.get("credentials", {}).items()},
        realtime=bool(raw_prices.get("realtime", False)),
        refresh_seconds=int(raw_prices.get("refresh_seconds", Prices.refresh_seconds)),
        min_refresh_seconds=int(raw_prices.get("min_refresh_seconds", Prices.min_refresh_seconds)),
    )
    return Config(
        user_agent=user_agent,
        database=Path(database).expanduser() if database else Config.database,
        requests_per_second=rps,
        prices=prices,
    )
