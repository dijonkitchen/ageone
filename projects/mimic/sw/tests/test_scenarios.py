"""Every scenario in scenarios.py on the golden model (cocotb runs them on the RTL too)."""

from __future__ import annotations

import pytest
import scenarios
from mimic.bench import run


@pytest.mark.parametrize("name", sorted(scenarios.ALL))
def test_scenario(name: str) -> None:
    run(scenarios.ALL[name])
