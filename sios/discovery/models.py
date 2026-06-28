"""Unified Opportunity model — the output of any Discovery Engine agent."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OpportunityType(str, Enum):
    # ── Financial (Value Engine) ─────────────────────────────────────────────
    FINANCIAL_SAVING = "financial_saving"
    DUPLICATE_PAYMENT = "duplicate_payment"
    UNUSED_SUBSCRIPTION = "unused_subscription"
    COST_ANOMALY = "cost_anomaly"
    CLOUD_WASTE = "cloud_waste"
    TAX_CREDIT = "tax_credit"
    PUBLIC_GRANT = "public_grant"

    # ── Knowledge (Discovery Engine) ─────────────────────────────────────────
    CROSS_DOMAIN_CONNECTION = "cross_domain_connection"
    BLIND_SPOT = "blind_spot"
    EMERGING_SIGNAL = "emerging_signal"
    SCIENTIFIC_CONTRADICTION = "scientific_contradiction"
    BREAKTHROUGH_PREDICTION = "breakthrough_prediction"

    # ── Business ─────────────────────────────────────────────────────────────
    MARKET_GAP = "market_gap"
    COMPLIANCE_RISK = "compliance_risk"


class OpportunityStatus(str, Enum):
    OPEN = "open"
    PROVING = "proving"       # CPO being generated
    PROVED = "proved"         # CPO attached
    EVALUATED = "evaluated"   # Value Score computed
    ACTIONED = "actioned"     # PVC minted
    DISMISSED = "dismissed"


class Opportunity(BaseModel):
    """
    The unified output of any Discovery Engine agent.

    Flows through:  Discovery → Proof Engine (CPO) → Value Engine (score) → PVC
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: OpportunityType
    title: str
    description: str
    confidence: float                          # 0.0 – 1.0

    # Financial dimension (may be None for knowledge opportunities)
    estimated_value: Optional[float] = None
    currency: str = "EUR"

    # Evidence and source
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)  # concepts / entities involved
    recommended_actions: List[str] = Field(default_factory=list)

    # Provenance
    discovery_engine: str = ""               # which engine/agent found this
    discovery_domain: str = ""               # "finance" | "science" | "business"
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    # Lifecycle
    status: OpportunityStatus = OpportunityStatus.OPEN
    cpo_id: Optional[str] = None             # Proof Engine output
    value_score: Optional[float] = None      # Value Engine output
    pvc_id: Optional[str] = None             # Final PVC

    metadata: Dict[str, Any] = Field(default_factory=dict)


class KGEntity(BaseModel):
    """A node in the Knowledge Graph."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str
    entity_type: str      # "concept" | "person" | "institution" | "technology" | "disease"
    sources: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    frequency: int = 1    # how many documents reference this entity
    metadata: Dict[str, Any] = Field(default_factory=dict)


class KGRelationship(BaseModel):
    """An edge in the Knowledge Graph."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_id: str
    to_id: str
    relation_type: str    # "cites" | "contradicts" | "extends" | "applies_to" | "co_occurs"
    strength: float       # 0.0 – 1.0
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
