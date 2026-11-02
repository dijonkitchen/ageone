from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from place_outcomes import features

DATA = Path(__file__).parent / "data"


@pytest.fixture
def con() -> Iterator[duckdb.DuckDBPyConnection]:
    connection = duckdb.connect()
    features.build(connection, DATA)
    yield connection
    connection.close()
