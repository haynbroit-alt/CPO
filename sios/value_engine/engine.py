"""ValueEngine — orchestrates all detectors and aggregates findings."""

from __future__ import annotations

from typing import Dict, List, Optional, Type

from sios.core.models import CanonicalTransaction, Finding
from sios.value_engine.base import BaseDetector
from sios.value_engine.detectors import (
    CloudWasteDetector,
    CostAnomalyDetector,
    DuplicatePaymentDetector,
    UnusedSubscriptionDetector,
)

_DEFAULT_DETECTORS: List[Type[BaseDetector]] = [
    DuplicatePaymentDetector,
    UnusedSubscriptionDetector,
    CostAnomalyDetector,
    CloudWasteDetector,
]


class ValueEngine:
    """Run all registered detectors against a transaction set.

    Example::

        from sios.value_engine.engine import ValueEngine
        from sios.core.ingestion import from_csv

        txns = from_csv(open("expenses.csv").read())
        engine = ValueEngine()
        findings = engine.run(txns)
        for f in findings:
            print(f.type, f.estimated_amount, f.confidence)
    """

    def __init__(self, detectors: Optional[List[BaseDetector]] = None) -> None:
        if detectors is not None:
            self._detectors = detectors
        else:
            self._detectors: List[BaseDetector] = [cls() for cls in _DEFAULT_DETECTORS]

    def run(self, transactions: List[CanonicalTransaction]) -> List[Finding]:
        """Execute all detectors and return deduplicated, confidence-sorted findings."""
        all_findings: List[Finding] = []
        for detector in self._detectors:
            try:
                all_findings.extend(detector.detect(transactions))
            except Exception:
                pass  # never let one detector crash the whole run

        all_findings.sort(key=lambda f: f.confidence, reverse=True)
        return all_findings

    def summary(self, findings: List[Finding]) -> Dict:
        """Return aggregate statistics over a list of findings."""
        total = sum(f.estimated_amount for f in findings)
        by_type: Dict[str, Dict] = {}
        for f in findings:
            k = f.type.value
            if k not in by_type:
                by_type[k] = {"count": 0, "estimated_amount": 0.0}
            by_type[k]["count"] += 1
            by_type[k]["estimated_amount"] += f.estimated_amount

        return {
            "total_findings": len(findings),
            "total_estimated_amount": round(total, 2),
            "currency": findings[0].currency if findings else "EUR",
            "by_type": by_type,
        }
