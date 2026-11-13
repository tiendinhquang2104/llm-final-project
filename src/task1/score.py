"""Exact hundredth-point arithmetic for Task 1 rubric scores."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


def to_cents(value: object, maximum: int) -> int:
    """Validate a JSON number on the 0.01 grid and return integer cents."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"invalid score: {value!r}")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"invalid score: {value!r}") from exc
    cents = number * 100
    if not cents.is_finite() or cents != cents.to_integral_value() or not 0 <= cents <= maximum * 100:
        raise ValueError(f"score must be 0..{maximum} in 0.01 increments: {value!r}")
    return int(cents)


def from_cents(cents: int) -> int | float:
    return cents // 100 if cents % 100 == 0 else cents / 100
