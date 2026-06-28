"""Detect cloud spending waste from transaction descriptions and metadata."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import List

from sios.core.models import CanonicalTransaction, Finding, FindingType
from sios.value_engine.base import BaseDetector


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
     "Cloud object storage charge — possible stale data",
     "Audit S3/Blob lifecycles; apply expiry policies on old objects"),
    (re.compile(r"\b(nat gateway|data transfer|egress|bandwidth)\b", re.IGNORECASE),
     "Network egress cost detected",
     "Review architecture for unnecessary cross-region data transfer"),
    (re.compile(r"\b(reserved|commitment|savings plan)\b", re.IGNORECASE),
     "Reserved instance or savings plan — check utilisation",
     "Verify that reserved capacity is being fully utilised"),
]


def _is_cloud(txn: CanonicalTransaction) -> bool:
    text = f"{txn.vendor} {txn.description}".lower()
    return bool(_CLOUD_VENDORS.search(text))


def _vendor_key(txn: CanonicalTransaction) -> str:
    m = _CLOUD_VENDORS.search(f"{txn.vendor} {txn.description}")
    return m.group(0).lower() if m else (txn.vendor or "cloud").lower()[:20]


class CloudWasteDetector(BaseDetector):
    """Identify cloud spending patterns that typically indicate waste:
    dev/test environments running 24/7, stale storage, egress overcharges."""

    name = "cloud_waste"

    def __init__(self, min_monthly_spend: float = 200.0) -> None:
        self.min_monthly_spend = min_monthly_spend

    def detect(self, transactions: List[CanonicalTransaction]) -> List[Finding]:
        cloud_txns = [t for t in transactions if _is_cloud(t) and t.amount > 0]
        if not cloud_txns:
            return []

        findings: List[Finding] = []

        # --- Pattern-based findings ------------------------------------------
        for txn in cloud_txns:
            text = f"{txn.vendor} {txn.description}"
            for pattern, reason, action in _WASTE_PATTERNS:
                if pattern.search(text):
                    f = Finding(
                        type=FindingType.CLOUD_WASTE,
                        title=f"Cloud waste signal — {reason}",
                        description=(
                            f"Transaction of {txn.amount:.2f} {txn.currency} "
                            f"on {txn.date.date()} matches a known cloud waste "
                            f"pattern: {reason}."
                        ),
                        estimated_amount=txn.amount * 0.4,
                        currency=txn.currency,
                        confidence=0.65,
                        evidence=[
                            {"transaction_id": txn.id, "date": txn.date.isoformat(),
                             "amount": txn.amount, "description": txn.description,
                             "pattern": pattern.pattern},
                        ],
                        recommended_actions=[action,
                                             "Tag all cloud resources with cost-centre and environment"],
                        related_transaction_ids=[txn.id],
                    )
                    findings.append(self._tag(f))
                    break

        # --- Aggregate: flag vendors with high total monthly spend -----------
        by_vendor: dict = defaultdict(list)
        for t in cloud_txns:
            by_vendor[_vendor_key(t)].append(t)

        for vendor, txns in by_vendor.items():
            if not txns:
                continue
            date_range_days = max(1, (max(t.date for t in txns) - min(t.date for t in txns)).days)
            monthly = sum(t.amount for t in txns) / max(date_range_days / 30, 1)
            if monthly < self.min_monthly_spend:
                continue

            f = Finding(
                type=FindingType.CLOUD_WASTE,
                title=f"High cloud spend — {vendor} (~{monthly:.0f}/month)",
                description=(
                    f"Detected ~{monthly:.2f} {txns[0].currency}/month in cloud "
                    f"spend on {vendor}. A FinOps review could typically recover "
                    f"15–30% through rightsizing and reservation."
                ),
                estimated_amount=monthly * 0.20,
                currency=txns[0].currency,
                confidence=0.70,
                evidence=[
                    {"vendor": vendor, "monthly_estimate": round(monthly, 2),
                     "transaction_count": len(txns)}
                ],
                recommended_actions=[
                    f"Run a cost optimisation report on {vendor}",
                    "Enable rightsizing recommendations",
                    "Purchase reserved instances for stable workloads (up to 72% savings)",
                    "Enable budget alerts to catch spikes early",
                ],
                related_transaction_ids=[t.id for t in txns],
            )
            findings.append(self._tag(f))

        return findings
