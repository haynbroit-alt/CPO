"""SIOS Proof Layer — AuditRecord with 3-layer truth model.

Truth Stack (from bottom to top):
  RAW DATA LAYER    — immutable snapshot, SHA-256 hashed
  DETECTION LAYER   — SIOS rules output, fully reproducible
  VERIFICATION LAYER — human/client validation, business truth
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VerificationLevel(str, Enum):
    CLIENT_VERIFIED = "client_verified"       # green — signed by client
    INTERNAL_ONLY = "internal_only"           # yellow — validated internally
    REPRODUCIBLE_ONLY = "reproducible_only"   # blue — no human validation yet


class AnomalyType(str, Enum):
    DUPLICATE_PAYMENT = "duplicate_payment"
    UNUSED_SUBSCRIPTION = "unused_subscription"
    UNUSED_LICENSE = "unused_license"
    CLOUD_WASTE = "cloud_waste"
    COST_ANOMALY = "cost_anomaly"
    TELECOM_OVERCHARGE = "telecom_overcharge"
    RENEGOTIABLE_CONTRACT = "renegotiable_contract"


class Sector(str, Enum):
    SAAS = "SaaS"
    RETAIL = "Retail"
    FINANCE = "Finance"
    MANUFACTURING = "Manufacturing"
    HEALTHCARE = "Healthcare"
    LOGISTICS = "Logistics"
    MEDIA = "Media"


# ---------------------------------------------------------------------------
# Truth Stack layers
# ---------------------------------------------------------------------------

class RawDataLayer(BaseModel):
    """Layer 1 — Immutable snapshot of input data."""
    dataset_hash: str                  # SHA-256 of canonical transaction set
    transaction_count: int
    ingested_at: datetime
    source: str                        # "csv", "stripe", "aws", "erp"
    period_months: int = 6
    immutable: bool = True


class DetectionLayer(BaseModel):
    """Layer 2 — SIOS detection output, reproducible by any third party."""
    model_version: str                 # e.g. "sios-v3.2"
    rules_applied: List[str]
    anomalies_found: int
    detection_hash: str                # SHA-256 of full detection output
    reproducible: bool = True
    drift_pct: float = 0.0             # % variance when replayed


class VerificationLayer(BaseModel):
    """Layer 3 — Business truth: human/client/accountant validation."""
    level: VerificationLevel
    client_approved: bool = False
    accountant_validated: bool = False
    legal_status: Optional[str] = None
    approved_at: Optional[datetime] = None
    approver_role: Optional[str] = None   # "CFO", "Finance Director", "Controller"
    signature_ref: Optional[str] = None   # document ref or hash


# ---------------------------------------------------------------------------
# Anomaly within an audit
# ---------------------------------------------------------------------------

class AuditAnomaly(BaseModel):
    """A single anomaly detected within an audit."""
    type: AnomalyType
    vendor: str                            # anonymized if public
    description: str
    estimated_amount: float
    confirmed_amount: Optional[float] = None
    currency: str = "EUR"
    trust_tier: str = "HIGH"               # LOW | MEDIUM | HIGH


# ---------------------------------------------------------------------------
# Audit artifact (technical evidence)
# ---------------------------------------------------------------------------

class AuditArtifact(BaseModel):
    """A technical artifact generated during the audit."""
    label: str
    artifact_type: str   # "query", "log", "hash", "signature", "export"
    value: str           # the actual content or hash
    generated_at: datetime


# ---------------------------------------------------------------------------
# Main AuditRecord
# ---------------------------------------------------------------------------

class AuditRecord(BaseModel):
    """Complete, verifiable audit record for the SIOS Proof Layer."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_number: int
    sector: str
    audit_date: datetime

    # Executive summary
    transactions_analyzed: int
    anomalies_detected: int
    estimated_savings_eur: float
    confirmed_savings_eur: Optional[float] = None
    confidence_pct: int = 95              # overall confidence score

    # Detailed anomalies
    anomalies: List[AuditAnomaly] = Field(default_factory=list)

    # Truth Stack (the 3 layers)
    raw_data: RawDataLayer
    detection: DetectionLayer
    verification: VerificationLayer

    # Timeline steps (for the Audit Viewer)
    timeline: List[Dict[str, Any]] = Field(default_factory=list)

    # Technical artifacts
    artifacts: List[AuditArtifact] = Field(default_factory=list)

    # Visibility
    is_public: bool = True
    client_token: Optional[str] = None    # vault access token
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @property
    def verification_badge(self) -> str:
        if self.verification.client_approved:
            return "client_verified"
        if self.verification.level == VerificationLevel.INTERNAL_ONLY:
            return "internal_only"
        return "reproducible_only"

    @property
    def savings_confirmed_pct(self) -> Optional[float]:
        if self.confirmed_savings_eur and self.estimated_savings_eur:
            return round(self.confirmed_savings_eur / self.estimated_savings_eur * 100, 1)
        return None
