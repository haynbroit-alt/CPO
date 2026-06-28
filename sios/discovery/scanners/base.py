"""Base scanner interface for all Discovery Engine sources."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import List

_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to",
    "for", "of", "with", "and", "or", "this", "that", "it", "we", "they",
    "he", "she", "by", "as", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "not", "no", "but", "from", "our", "their", "its", "also",
    "using", "used", "into", "than", "then", "which", "when", "where",
    "how", "what", "who", "show", "shows", "paper", "study", "model",
    "results", "data", "based", "method", "approach", "new", "novel",
})


class RawDocument:
    """Source-agnostic document extracted by a scanner."""

    __slots__ = ("source", "source_id", "title", "body", "url", "domain", "metadata")

    def __init__(
        self,
        source: str,
        title: str,
        body: str = "",
        url: str = "",
        source_id: str = "",
        domain: str = "",
        metadata: dict | None = None,
    ) -> None:
        self.source = source
        self.source_id = source_id
        self.title = title
        self.body = body
        self.url = url
        self.domain = domain
        self.metadata = metadata or {}

    @property
    def concepts(self) -> List[str]:
        text = f"{self.title} {self.body}"
        words = re.findall(r"[A-Z][a-z]{2,}|[a-z]{4,}", text)
        seen: dict = {}
        for w in words:
            key = w.lower()
            if key not in _STOPWORDS:
                seen[key] = seen.get(key, 0) + 1
        return sorted(seen, key=seen.get, reverse=True)[:15]  # type: ignore[arg-type]

    def __repr__(self) -> str:
        return f"<RawDocument source={self.source!r} title={self.title[:40]!r}>"


class BaseScanner(ABC):
    """All scanners implement this interface."""

    source_name: str = "base"

    @abstractmethod
    def scan(self, **kwargs) -> List[RawDocument]:
        """Fetch documents from the source and return RawDocument list."""
        ...
