"""Detect recurring charges that appear unused (no usage signal in the window)."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import timedelta
from typing import List

from sios.core.models import CanonicalTransaction, Finding, FindingType
from sios.value_engine.base import BaseDetector
from sios.value_engine.trust import (
    estimate_range,
    signal_consistency,
    trust_score,
    trust_tier,
)


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
]

# Cloud vendors are handled by CloudWasteDetector — exclude here to avoid double-count
_CLOUD_VENDORS = re.compile(
    r"\b(aws|amazon web|azure|google cloud|gcp|digitalocean|linode|hetzner|"
    r"ovh|scaleway|render|fly\.io|railway)\b",
    re.IGNORECASE,
)


def _is_subscription(txn: CanonicalTransaction) -> bool:
    text = f"{txn.vendor} {txn.description}".lower()
    if any(kw in text for kw in _SUBSCRIPTION_KEYWORDS):
        return True
    return any(re.search(pat, text) for pat in _VENDOR_PATTERNS)


def _is_cloud_vendor(txn: CanonicalTransaction) -> bool:
    return bool(_CLOUD_VENDORS.search(f"{txn.vendor} {txn.description}"))


def _vendor_key(txn: CanonicalTransaction) -> str:
    return (txn.vendor or txn.description or "").lower().strip()[:40]


def _months_covered(txns: List[CanonicalTransaction]) -> float:
    if len(txns) < 2:
        return 1.0
    delta = max(t.date for t in txns) - min(t.date for t in txns)
    return max(delta.days / 30.0, 1.0)


class UnusedSubscriptionDetector(BaseDetector):
    """Flag recurring SaaS charges for review with CFO-grade trust scoring.

    Cloud vendors (AWS, Azure, GCP…) are excluded here — handled by
    CloudWasteDetector — to prevent double-counting.
    """

    name = "unused_subscription"

    def __init__(
        self,
        min_occurrences: int = 2,
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
            and not _is_cloud_vendor(t)   # defer cloud to CloudWasteDetector
        ]

        by_vendor: dict = defaultdict(list)
        for t in candidates:
            by_vendor[_vendor_key(t)].append(t)

        findings: List[Finding] = []
        for vendor, txns in by_vendor.items():
            if len(txns) < self.min_occurrences:
                continue
            txns.sort(key=lambda t: t.date)

            amounts = [t.amount for t in txns]
            observed_total = sum(amounts)
            avg_amount = observed_total / len(txns)
            months = _months_covered(txns)

            consistency = signal_consistency(amounts)
            total_txns_in_dataset = len(transactions)
            coverage = min(months / 12.0, 1.0)

            ts = trust_score(total_txns_in_dataset, consistency, coverage)
            tier = trust_tier(ts)

            ranges = estimate_range(observed_total, len(txns), months)

            if tier == "LOW":
                # Signal only — no € estimate
                desc = (
                    f"Recurring charge pattern detected for '{vendor}' "
                    f"({len(txns)} occurrences over {months:.0f} months). "
                    f"Insufficient data for a reliable estimate — "
                    f"upload 6+ months of transactions for quantified savings."
                )
                estimated = 0.0
            elif tier == "MEDIUM":
                desc = (
                    f"Detected {len(txns)} recurring charges to '{vendor}' "
                    f"(avg {avg_amount:.0f} {txns[0].currency}/charge, "
                    f"{months:.0f} months observed). "
                    f"Estimated recoverable: "
                    f"{ranges['low']:.0f}–{ranges['high']:.0f} {txns[0].currency}. "
                    f"Review whether this subscription is actively used."
                )
                estimated = ranges["mid"]
            else:  # HIGH
                desc = (
                    f"Detected {len(txns)} recurring charges to '{vendor}' "
                    f"(avg {avg_amount:.0f} {txns[0].currency}/charge). "
                    f"Statistical analysis indicates "
                    f"{ranges['low']:.0f}–{ranges['high']:.0f} {txns[0].currency} "
                    f"is recoverable through cancellation or renegotiation."
                )
                estimated = ranges["mid"]

            f = Finding(
                type=FindingType.UNUSED_SUBSCRIPTION,
                title=f"Recurring subscription — {vendor}",
                description=desc,
                estimated_amount=estimated,
                currency=txns[0].currency,
                confidence=round(ts / 100.0, 2),
                trust_score=ts,
                trust_tier=tier,
                estimate_low=ranges["low"] if tier != "LOW" else None,
                estimate_high=ranges["high"] if tier != "LOW" else None,
                observed_value=round(observed_total, 2),
                observed_period=f"{months:.0f} months",
                evidence=[
                    {"transaction_id": t.id, "date": t.date.isoformat(),
                     "amount": t.amount, "description": t.description}
                    for t in txns[-6:]
                ],
                recommended_actions=[
                    f"Audit usage of '{vendor}' across the team",
                    "Cancel if no active users identified",
                    "Negotiate annual rate or downgrade tier",
                ],
                related_transaction_ids=[t.id for t in txns],
            )
            findings.append(self._tag(f))

        return findings
