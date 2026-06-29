"""Detect cloud spending waste from transaction descriptions and metadata."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import List

from sios.core.models import CanonicalTransaction, Finding, FindingType
from sios.value_engine.base import BaseDetector
from sios.value_engine.trust import (
    estimate_range,
    signal_consistency,
    trust_score,
    trust_tier,
)


_CLOUD_VENDORS = re.compile(
    r"\b(aws|amazon web|azure|google cloud|gcp|digitalocean|linode|hetzner|"
    r"ovh|scaleway|render|fly\.io|railway)\b",
    re.IGNORECASE,
)

_WASTE_PATTERNS = [
    (re.compile(r"\b(dev|test|staging|sandbox|poc)\b", re.IGNORECASE),
     "Non-production environment running continuously",
     "Stop/hibernate dev environments outside business hours (saves ~65%)"),
    (re.compile(r"\bstorage\b.*\b(s3|blob|gcs|bucket)\b", re.IGNORECASE),
     "Cloud object storage — possible stale data",
     "Audit S3/Blob lifecycles; apply expiry policies on old objects"),
    (re.compile(r"\b(nat gateway|data transfer|egress|bandwidth)\b", re.IGNORECASE),
     "Network egress cost detected",
     "Review architecture for unnecessary cross-region data transfer"),
    (re.compile(r"\b(reserved|commitment|savings plan)\b", re.IGNORECASE),
     "Reserved instance — check utilisation",
     "Verify that reserved capacity is being fully utilised"),
]


def _is_cloud(txn: CanonicalTransaction) -> bool:
    return bool(_CLOUD_VENDORS.search(f"{txn.vendor} {txn.description}"))


def _vendor_key(txn: CanonicalTransaction) -> str:
    m = _CLOUD_VENDORS.search(f"{txn.vendor} {txn.description}")
    return m.group(0).lower() if m else (txn.vendor or "cloud").lower()[:20]


def _months_covered(txns: List[CanonicalTransaction]) -> float:
    if len(txns) < 2:
        return 1.0
    delta = max(t.date for t in txns) - min(t.date for t in txns)
    return max(delta.days / 30.0, 1.0)


class CloudWasteDetector(BaseDetector):
    """Identify cloud spending patterns that typically indicate waste.

    Produces one aggregate finding per cloud vendor with a trust-scored
    range estimate. Pattern-based signals (dev/test envs) are folded into
    the aggregate rather than generating separate line items, to avoid
    inflating the total.
    """

    name = "cloud_waste"

    def __init__(self, min_monthly_spend: float = 100.0) -> None:
        self.min_monthly_spend = min_monthly_spend

    def detect(self, transactions: List[CanonicalTransaction]) -> List[Finding]:
        cloud_txns = [t for t in transactions if _is_cloud(t) and t.amount > 0]
        if not cloud_txns:
            return []

        total_txns = len(transactions)

        by_vendor: dict = defaultdict(list)
        for t in cloud_txns:
            by_vendor[_vendor_key(t)].append(t)

        findings: List[Finding] = []

        for vendor, txns in by_vendor.items():
            txns_sorted = sorted(txns, key=lambda t: t.date)
            months = _months_covered(txns_sorted)
            observed_total = sum(t.amount for t in txns_sorted)
            monthly_avg = observed_total / max(months, 1.0)

            if monthly_avg < self.min_monthly_spend:
                continue

            # Detect waste patterns present in this vendor's transactions
            patterns_hit = []
            for txn in txns_sorted:
                text = f"{txn.vendor} {txn.description}"
                for pattern, reason, action in _WASTE_PATTERNS:
                    if pattern.search(text) and reason not in patterns_hit:
                        patterns_hit.append(reason)

            # Signal strength: pattern hits + consistency
            amounts = [t.amount for t in txns_sorted]
            consistency = signal_consistency(amounts)
            has_pattern = len(patterns_hit) > 0
            # Pattern hit boosts signal strength
            sig_strength = min(1.0, consistency + (0.25 if has_pattern else 0))

            coverage = min(months / 12.0, 1.0)
            ts = trust_score(total_txns, sig_strength, coverage)
            tier = trust_tier(ts)

            ranges = estimate_range(observed_total, len(txns_sorted), months)

            pattern_note = ""
            if patterns_hit:
                pattern_note = " Waste signals: " + "; ".join(patterns_hit) + "."

            if tier == "LOW":
                desc = (
                    f"Cloud spend detected on {vendor} — "
                    f"{len(txns_sorted)} charge(s), "
                    f"{observed_total:.0f} {txns_sorted[0].currency} observed.{pattern_note} "
                    f"Insufficient data for a reliable savings estimate. "
                    f"Upload 6+ months of statements for quantified analysis."
                )
                estimated = 0.0
            elif tier == "MEDIUM":
                desc = (
                    f"Cloud spend on {vendor}: ~{monthly_avg:.0f} {txns_sorted[0].currency}/month "
                    f"observed over {months:.0f} months.{pattern_note} "
                    f"Estimated recoverable through FinOps review: "
                    f"{ranges['low']:.0f}–{ranges['high']:.0f} {txns_sorted[0].currency}."
                )
                estimated = ranges["mid"]
            else:
                desc = (
                    f"Cloud spend on {vendor}: ~{monthly_avg:.0f} {txns_sorted[0].currency}/month.{pattern_note} "
                    f"Statistical analysis: {ranges['low']:.0f}–{ranges['high']:.0f} "
                    f"{txns_sorted[0].currency} recoverable through rightsizing and reservation."
                )
                estimated = ranges["mid"]

            actions = [
                f"Run a cost optimisation report on {vendor}",
                "Enable rightsizing recommendations",
                "Purchase reserved instances for stable workloads",
                "Enable budget alerts to catch spikes early",
            ]
            if has_pattern:
                actions.insert(0, "Stop/hibernate non-production environments outside business hours")

            f = Finding(
                type=FindingType.CLOUD_WASTE,
                title=f"Cloud spend review — {vendor}",
                description=desc,
                estimated_amount=estimated,
                currency=txns_sorted[0].currency,
                confidence=round(ts / 100.0, 2),
                trust_score=ts,
                trust_tier=tier,
                estimate_low=ranges["low"] if tier != "LOW" else None,
                estimate_high=ranges["high"] if tier != "LOW" else None,
                observed_value=round(observed_total, 2),
                observed_period=f"{months:.0f} months",
                evidence=[
                    {"vendor": vendor,
                     "monthly_avg": round(monthly_avg, 2),
                     "observed_total": round(observed_total, 2),
                     "transaction_count": len(txns_sorted),
                     "patterns_detected": patterns_hit}
                ],
                recommended_actions=actions[:4],
                related_transaction_ids=[t.id for t in txns_sorted],
            )
            findings.append(self._tag(f))

        return findings
