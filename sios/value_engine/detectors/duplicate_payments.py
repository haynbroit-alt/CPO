"""Detect duplicate payments: same vendor + similar amount within a time window."""

from __future__ import annotations

from datetime import timedelta
from typing import List

from sios.core.models import CanonicalTransaction, Finding, FindingType
from sios.value_engine.base import BaseDetector


class DuplicatePaymentDetector(BaseDetector):
    """Flag transactions that appear twice within ``window_days`` with the same
    vendor and amount (within ``amount_tolerance`` percent)."""

    name = "duplicate_payment"

    def __init__(
        self,
        window_days: int = 7,
        amount_tolerance: float = 0.01,
        min_amount: float = 10.0,
    ) -> None:
        self.window = timedelta(days=window_days)
        self.tol = amount_tolerance
        self.min_amount = min_amount

    def detect(self, transactions: List[CanonicalTransaction]) -> List[Finding]:
        debits = [t for t in transactions if t.amount >= self.min_amount]
        debits.sort(key=lambda t: t.date)

        findings: List[Finding] = []
        seen_pairs: set = set()

        for i, t1 in enumerate(debits):
            for t2 in debits[i + 1:]:
                if t2.date - t1.date > self.window:
                    break
                pair_key = tuple(sorted([t1.id, t2.id]))
                if pair_key in seen_pairs:
                    continue
                if not self._same_vendor(t1, t2):
                    continue
                if not self._similar_amount(t1.amount, t2.amount):
                    continue

                seen_pairs.add(pair_key)
                est = min(t1.amount, t2.amount)
                confidence = self._confidence(t1, t2)

                f = Finding(
                    type=FindingType.DUPLICATE_PAYMENT,
                    title=f"Possible duplicate payment — {t1.vendor or t1.description}",
                    description=(
                        f"Two transactions of similar amount ({t1.amount:.2f} and "
                        f"{t2.amount:.2f} {t1.currency}) to the same vendor "
                        f"within {(t2.date - t1.date).days} day(s)."
                    ),
                    estimated_amount=est,
                    currency=t1.currency,
                    confidence=confidence,
                    evidence=[
                        {"transaction_id": t1.id, "date": t1.date.isoformat(),
                         "amount": t1.amount, "description": t1.description},
                        {"transaction_id": t2.id, "date": t2.date.isoformat(),
                         "amount": t2.amount, "description": t2.description},
                    ],
                    recommended_actions=[
                        "Compare both transaction receipts",
                        "Contact vendor to request refund of duplicate charge",
                        "Block future duplicate at payment gateway level",
                    ],
                    related_transaction_ids=[t1.id, t2.id],
                )
                findings.append(self._tag(f))

        return findings

    def _same_vendor(self, t1: CanonicalTransaction, t2: CanonicalTransaction) -> bool:
        v1 = (t1.vendor or t1.description or "").lower().strip()
        v2 = (t2.vendor or t2.description or "").lower().strip()
        if not v1 or not v2:
            return False
        if v1 == v2:
            return True
        # substring match for common abbreviations
        shorter, longer = sorted([v1, v2], key=len)
        return shorter and shorter in longer

    def _similar_amount(self, a: float, b: float) -> bool:
        if a == 0 or b == 0:
            return False
        return abs(a - b) / max(a, b) <= self.tol

    def _confidence(self, t1: CanonicalTransaction, t2: CanonicalTransaction) -> float:
        exact_vendor = (t1.vendor or "").lower() == (t2.vendor or "").lower()
        exact_amount = t1.amount == t2.amount
        days_apart = abs((t2.date - t1.date).days)
        base = 0.6
        if exact_vendor:
            base += 0.2
        if exact_amount:
            base += 0.15
        if days_apart == 0:
            base += 0.05
        return min(base, 0.99)
