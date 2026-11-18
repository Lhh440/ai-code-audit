from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, TypeVar

T = TypeVar("T")


class Repo(Protocol[T]):
    def get(self, key: str) -> T | None: ...


@dataclass(frozen=True)
class Money:
    cents: int
    currency: str = "usd"
    tags: tuple[str, ...] = field(default_factory=tuple)

    def plus(self, other: Money) -> Money:
        if other.currency != self.currency:
            raise ValueError("currency mismatch")
        return Money(self.cents + other.cents, self.currency)


def total(items: list[Money]) -> Money:
    if not items:
        return Money(0)
    head, *rest = items
    for item in rest:
        head = head.plus(item)
    return head
