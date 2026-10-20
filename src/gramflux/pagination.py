"""Validation shared by bounded, demand-driven API pagination."""

from collections import deque
from collections.abc import Sequence
from typing import TypeAlias

from .errors import ConfigurationError

MessageIDs: TypeAlias = int | Sequence[int]


def count(value: int | None, *, name: str = "limit", allow_none: bool = True) -> None:
    if value is None and allow_none:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConfigurationError(
            f"{name} must be a nonnegative integer" + (" or None" if allow_none else "")
        )


def page_size(value: int, maximum: int = 100) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
        raise ConfigurationError(f"page_size must be between 1 and {maximum}")


def message_ids(value: MessageIDs, *, maximum: int = 10000) -> list[int]:
    if not isinstance(value, int) and (
        not isinstance(value, Sequence) or isinstance(value, (str, bytes))
    ):
        raise ConfigurationError("message IDs must be an integer or sequence of integers")
    if not isinstance(value, int) and len(value) > maximum:
        raise ConfigurationError(f"provide at most {maximum} message IDs")
    values = [value] if isinstance(value, int) else list(value)
    if not values or len(values) > maximum:
        raise ConfigurationError(f"provide between 1 and {maximum} message IDs")
    if any(isinstance(v, bool) or not isinstance(v, int) or not 0 < v < 2**31 for v in values):
        raise ConfigurationError("message IDs must be positive signed 32-bit integers")
    return values


class RecentIDs:
    """Bounded overlap suppression, not a durable/global deduplication claim."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._order: deque[int] = deque()
        self._known: set[int] = set()

    def add(self, ident: int) -> bool:
        if ident in self._known:
            return False
        self._known.add(ident)
        self._order.append(ident)
        if len(self._order) > self.capacity:
            self._known.remove(self._order.popleft())
        return True
