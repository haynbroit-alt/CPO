"""Base class for all Value Engine detectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from sios.core.models import CanonicalTransaction, Finding


class BaseDetector(ABC):
    """All detectors implement this interface."""

    name: str = "base"

    @abstractmethod
    def detect(self, transactions: List[CanonicalTransaction]) -> List[Finding]:
        """Run detection and return zero or more Findings."""
        ...

    def _tag(self, finding: Finding) -> Finding:
        finding.detector = self.name
        return finding
