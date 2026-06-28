"""Detect recurring charges that appear unused (no usage signal in the window)."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import timedelta
from typing import List

from sios.core.models import CanonicalTransaction, Finding, FindingType
from sios.value_engine.base import BaseDetector


_SUBSCRIPTION_KEYWORDS = [
    "abonnement", "subscription", "saas", "mensuel", "monthly", "annual",
    "yearly", "licence", "license", "plan", "forfait", "software",
]

_VENDOR_PATTERNS = [
    r"\bslack\b", r"\bnotion\b", r"\bfigma\b", r"\blinear\b", r"\bjira\b",
    r"\bconfluence\b", r"\bzoom\b", r"\bteams\b", r"\bgithub\b", r"\bgitlab\b",
    r"\bheroku\b", r"\bvercel\b", r"\bnetlify\b", r"\bsentry\b", r"\bdatadog\b",
    r"\bnewrelic\b", r"\bpagerduty\b", r"\bintercom\b", r"\bhubspot\b",
    r"\bsalesforce\b", r"\bzendesk\b", r"\bfreshdesk\b", r"\bcloudflare\b",
    r"\baws\b", r"\bazure\b", r"\bgcp\b", r"\bgoogle cloud\b",
]


def _is_subscription(txn: CanonicalTransaction) -> bool:
    text = f"{txn.vendor} {txn.description}".lower()
    if any(kw in text for kw in _SUBSCRIPTION_KEYWORDS):
        return True
    return any(re.search(pat, text) for pat in _VENDOR_PATTERNS)


def _vendor_key(txn: CanonicalTransaction) -> str:
    return (txn.vendor or txn.description or "").lower().strip()[:40]


class UnusedSubscriptionDetector(BaseDetector):
    """Flag recurring charges where the same vendor appears every month but
    no corresponding usage/login signal exists.

    Without usage telemetry, we identify candidates as subscriptions that
    recur consistently and flag them for review with a lower confidence score.
    """

    name = "unused_subscription"

    def __init__(
        self,
        min_occurrences: int = 3,
        max_amount: float = 5000.0,
        lookback_days: int = 180,
    ) -> None:
        self.min_occurrences = min_occurrences
        self.max_amount = max_amount
        self.lookback_days = lookback_days

    def detect(self, transactions: List[CanonicalTransaction]) -> List[Finding]:
        if not transactions:
            return []

        latest = max(t.date for t in transactions)
        cutoff = latest - timedelta(days=self.lookback_days)
        candidates = [
            t for t in transactions
            if t.date >= cutoff
            and t.amount <= self.max_amount
            and t.amount > 0
            and _is_subscription(t)
        ]

        by_vendor: dict = defaultdict(list)
        for t in candidates:
            by_vendor[_vendor_key(t)].append(t)

        findings: List[Finding] = []
        for vendor, txns in by_vendor.items():
            if len(txns) < self.min_occurrences:
                continue
            txns.sort(key=lambda t: t.date)
            avg_amount = sum(t.amount for t in txns) / len(txns)
            annual_estimate = avg_amount * 12
            confidence = min(0.5 + 0.05 * len(txns), 0.8)

            f = Finding(
                type=FindingType.UNUSED_SUBSCRIPTION,
                title=f"Recurring subscription to review — {vendor}",
                description=(
                    f"Detected {len(txns)} recurring charges averaging "
                    f"{avg_amount:.2f} {txns[0].currency}/month to '{vendor}'. "
                    f"Estimated annual spend: {annual_estimate:.2f}. "
                    f"Review whether this subscription is actively used."
                ),
                estimated_amount=annual_estimate,
                currency=txns[0].currency,
                confidence=confidence,
                evidence=[
                    {"transaction_id": t.id, "date": t.date.isoformat(),
                     "amount": t.amount, "description": t.description}
                    for t in txns[-6:]
                ],
                recommended_actions=[
                    f"Audit usage of '{vendor}' across the team",
                    "Cancel if no active users can be identified",
                    "Negotiate annual rate or downgrade tier",
                    "Consolidate duplicate tool covering same need",
                ],
                related_transaction_ids=[t.id for t in txns],
            )
            findings.append(self._tag(f))

        return findings
