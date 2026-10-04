"""Local settings: the SEC contact (never committed) and where the database lives."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATHS = (
    PROJECT_DIR / "config.toml",
    Path.home() / ".config" / "ageone" / "stock-screener.toml",
)


@dataclass(frozen=True)
class Config:
    user_agent: str | None = None
    database: Path = PROJECT_DIR / "screener.duckdb"
    requests_per_second: float = 8.0

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
    return Config(
        user_agent=user_agent,
        database=Path(database).expanduser() if database else Config.database,
        requests_per_second=rps,
    )
