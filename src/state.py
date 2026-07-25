from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import TypeVar


T = TypeVar("T")


def valid_choice(
    value: T | None,
    options: Sequence[T],
    *,
    default: T | None = None,
) -> T | None:
    """Return a valid widget value when options change between reruns."""
    if value in options:
        return value
    if default in options:
        return default
    return options[0] if options else None


def valid_multi(values: Iterable[T] | None, options: Sequence[T]) -> list[T]:
    """Drop stale multiselect values while preserving the current option order."""
    selected = set(values or [])
    return [option for option in options if option in selected]
