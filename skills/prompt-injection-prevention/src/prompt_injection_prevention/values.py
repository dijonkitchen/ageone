"""Values tagged with where they came from and who may read them (CaMeL's capabilities)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True)
class Source:
    """Where a value came from. Only the people and code that run the program are trusted."""

    name: str
    trusted: bool


USER = Source("user", trusted=True)


class Readers:
    """Who may receive a value: everyone, or a fixed set of names such as email addresses."""

    __slots__ = ("names",)

    def __init__(self, names: Iterable[str] | None = None) -> None:
        self.names: frozenset[str] | None = None if names is None else frozenset(names)

    def allows(self, reader: str) -> bool:
        return self.names is None or reader in self.names

    def __and__(self, other: Readers) -> Readers:
        if self.names is None:
            return other
        if other.names is None:
            return self
        return Readers(self.names & other.names)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Readers) and self.names == other.names

    def __hash__(self) -> int:
        return hash(self.names)

    def __repr__(self) -> str:
        return "Readers.everyone" if self.names is None else f"Readers({sorted(self.names)})"


EVERYONE = Readers()


@dataclass(frozen=True)
class Value(Generic[T]):
    """A value with its sources and readers. Anything computed from it must carry both forward."""

    value: T
    sources: frozenset[Source] = field(default_factory=lambda: frozenset({USER}))
    readers: Readers = EVERYONE

    @property
    def trusted(self) -> bool:
        """True only if every source is trusted."""
        return all(s.trusted for s in self.sources)

    def derive(self, value: U, *others: Value[Any]) -> Value[U]:
        """A new value computed from this one (and others): union of sources, intersection of readers."""
        sources = self.sources.union(*(o.sources for o in others))
        readers = self.readers
        for o in others:
            readers = readers & o.readers
        return Value(value, sources, readers)


def trusted(value: T, readers: Readers = EVERYONE) -> Value[T]:
    """A value the user or the program supplied."""
    return Value(value, frozenset({USER}), readers)


def untrusted(value: T, source: str, readers: Readers = EVERYONE) -> Value[T]:
    """A value read from outside: a web page, an email, a file, a tool's output."""
    return Value(value, frozenset({Source(source, trusted=False)}), readers)
