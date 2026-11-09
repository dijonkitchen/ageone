"""Month arithmetic on first-of-month dates."""

from datetime import date


def add(d: date, months: int) -> date:
    total = d.year * 12 + d.month - 1 + months
    return date(total // 12, total % 12 + 1, 1)


def first_of(d: date) -> date:
    return d.replace(day=1)


def between(a: date, b: date) -> int:
    """Whole months from a to b."""
    return (b.year - a.year) * 12 + b.month - a.month
