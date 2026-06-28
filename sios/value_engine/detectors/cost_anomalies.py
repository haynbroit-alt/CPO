"""Detect cost anomalies using IQR-based statistical outlier detection."""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import List, Tuple

from sios.core.models import CanonicalTransaction, Finding, FindingType
from sios.value_engine.base import BaseDetector


def _iqr_bounds(values: List[float], k: float = 1.5) -> Tuple[float, float]:
    """Return (lower, upper) IQR fence."""
    n = len(values)
    if n < 4:
        return float("-inf"), float("inf")
    sorted_vals = sorted(values)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    iqr = q3 - q1
    return q1 - k * iqr, q3 + k * iqr


def _vendor_key(txn: CanonicalTransaction) -> str:
    return (txn.vendor or txn.description or "").lower().strip()[:40]


class CostAnomalyDetector(BaseDetector):
    """Flag individual transactions that are statistical outliers for their
    vendor, based on the IQR method applied to the vendor's transaction history."""

    name = "cost_anomaly"

    def __init__(
        self,
        min_history: int = 5,
        iqr_k: float = 2.0,
        min_amount: float = 50.0,
    ) -> None:
        self.min_history = min_history
        self.iqr_k = iqr_k
        self.min_amount = min_amount

    def detect(self, transactions: List[CanonicalTransaction]) -> List[Finding]:
        by_vendor: dict = defaultdict(list)
        for t in transactions:
            if t.amount >= self.min_amount:
                by_vendor[_vendor_key(t)].append(t)

        findings: List[Finding] = []
        for vendor, txns in by_vendor.items():
            if len(txns) < self.min_history:
                continue

            amounts = [t.amount for t in txns]
            _, upper = _iqr_bounds(amounts, self.iqr_k)
            mean = statistics.mean(amounts)

            for t in txns:
                if t.amount <= upper:
                    continue
                excess = t.amount - mean
                confidence = min(0.6 + 0.1 * ((t.amount - upper) / (upper - mean + 1e-9)), 0.92)

                f = Finding(
                    type=FindingType.COST_ANOMALY,
                    title=f"Abnormal charge — {vendor}",
                    description=(
                        f"Transaction of {t.amount:.2f} {t.currency} on "
                        f"{t.date.date()} from '{vendor}' is significantly above "
                        f"the historical average of {mean:.2f} for this vendor "
                        f"(IQR upper fence: {upper:.2f}). Excess: ~{excess:.2f}."
                    ),
                    estimated_amount=excess,
                    currency=t.currency,
                    confidence=confidence,
                    evidence=[
                        {"transaction_id": t.id, "date": t.date.isoformat(),
                         "amount": t.amount, "mean": round(mean, 2),
                         "iqr_upper": round(upper, 2), "excess": round(excess, 2)},
                    ],
                    recommended_actions=[
                        "Request itemised invoice from vendor",
                        "Check for one-time overage or billing error",
                        "Verify that the service usage spike is expected",
                        "Dispute with vendor if charge cannot be explained",
                    ],
                    related_transaction_ids=[t.id],
                )
                findings.append(self._tag(f))

        return findings
