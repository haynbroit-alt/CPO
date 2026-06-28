"""SIOS canonical data model — source-agnostic financial primitives."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    TRANSFER = "transfer"
    SUBSCRIPTION = "subscription"
    REFUND = "refund"
    UNKNOWN = "unknown"


class CanonicalTransaction(BaseModel):
    """Source-agnostic representation of a financial transaction."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str                         # "stripe", "csv", "pennylane", …
    source_id: Optional[str] = None     # original ID in the source system
    amount: float
    currency: str = "EUR"
    date: datetime
    description: str = ""
    vendor: str = ""
    category: Optional[str] = None
    transaction_type: TransactionType = TransactionType.UNKNOWN
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class FindingType(str, Enum):
    DUPLICATE_PAYMENT = "duplicate_payment"
    UNUSED_SUBSCRIPTION = "unused_subscription"
    COST_ANOMALY = "cost_anomaly"
    CLOUD_WASTE = "cloud_waste"
    TAX_CREDIT = "tax_credit"
    PUBLIC_GRANT = "public_grant"
    RENEGOTIABLE_CONTRACT = "renegotiable_contract"
    TELECOM_OVERCHARGE = "telecom_overcharge"
    UNUSED_LICENSE = "unused_license"


class FindingStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RECOVERED = "recovered"
    DISMISSED = "dismissed"


class Finding(BaseModel):
    """A detected economic opportunity."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: FindingType
    title: str
    description: str
    estimated_amount: float
    currency: str = "EUR"
    confidence: float                   # 0.0 – 1.0
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    related_transaction_ids: List[str] = Field(default_factory=list)
    status: FindingStatus = FindingStatus.OPEN
    detector: str = ""                  # name of the detector that produced this
    detected_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RecoveryProof(BaseModel):
    """Evidence that a Finding was actually recovered."""

    document_refs: List[str] = Field(default_factory=list)
    data_refs: List[str] = Field(default_factory=list)
    recovered_amount: float
    recovered_at: datetime
    notes: str = ""


class PVC(BaseModel):
    """Proof of Value Creation — links a Finding to its verified recovery."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_id: str
    cpo_id: Optional[str] = None        # Proof Protocol CPO (execution proof)
    recovery_proof: RecoveryProof
    beneficiary: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    signature: Optional[str] = None     # Ed25519 over canonical(PVC)
    signer: Optional[str] = None        # node public key hex
