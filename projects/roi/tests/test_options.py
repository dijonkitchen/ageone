from datetime import date

import pytest

from roi.adapters import InMemoryOptionQuotes
from roi.domain import (
    AssetKind,
    OptionContract,
    OptionQuote,
    OptionRight,
    Security,
)
from roi.pricing import parity_scan, parity_violations

EXPIRY = date(2025, 1, 1)
ASOF = date(2024, 1, 1)


def option(strike: float, right: OptionRight) -> Security:
    contract = OptionContract("XYZ", EXPIRY, strike, right)
    tag = "C" if right is OptionRight.CALL else "P"
    return Security(f"XYZ{strike:g}{tag}", kind=AssetKind.OPTION, option=contract)


def quote(strike: float, right: OptionRight, mid: float) -> OptionQuote:
    return OptionQuote(option(strike, right), bid=mid - 0.05, ask=mid + 0.05, last=mid)


@pytest.mark.criteria("OPT-4")
def test_option_quote_rejects_equity() -> None:
    with pytest.raises(ValueError):
        OptionQuote(Security("XYZ"), bid=1, ask=2, last=1.5)


def test_option_quote_mid_falls_back_to_last() -> None:
    q = OptionQuote(option(100, OptionRight.CALL), bid=0.0, ask=0.0, last=3.3)
    assert q.mid == 3.3


@pytest.mark.criteria("OPT-3")
def test_parity_scan_flags_only_misaligned() -> None:
    # r=0 -> forward = S - K. Strike 100: C=P=8 -> residual 0 (aligned).
    # Strike 110: forward = -10, aligned needs C-P=-10. C=2,P=15 -> residual -3.
    quotes = [
        quote(100, OptionRight.CALL, 8.0),
        quote(100, OptionRight.PUT, 8.0),
        quote(110, OptionRight.CALL, 2.0),
        quote(110, OptionRight.PUT, 15.0),
    ]
    results = parity_scan(quotes, spot=100, rate=0.0, asof=ASOF, tolerance=0.5)
    by_strike = {r.strike: r for r in results}
    assert by_strike[100].aligned is True
    assert by_strike[100].residual == pytest.approx(0.0)
    assert by_strike[110].aligned is False
    assert by_strike[110].residual == pytest.approx(-3.0)

    violations = parity_violations(results)
    assert [r.strike for r in violations] == [110.0]


@pytest.mark.criteria("OPT-3")
def test_parity_scan_ignores_unpaired_contracts() -> None:
    results = parity_scan(
        [quote(100, OptionRight.CALL, 8.0)],  # no matching put
        spot=100,
        rate=0.0,
        asof=ASOF,
        tolerance=0.5,
    )
    assert results == []


def test_in_memory_option_quotes_groups_by_underlying() -> None:
    quotes = [quote(100, OptionRight.CALL, 8.0), quote(100, OptionRight.PUT, 8.0)]
    provider = InMemoryOptionQuotes(quotes)
    assert len(provider.chain(Security("XYZ"))) == 2
    assert provider.chain(Security("OTHER")) == ()
