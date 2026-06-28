"""Swarm data model — Spore, SporeLineage, FitnessSignal."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SporeStatus(str, Enum):
    PROPOSED = "proposed"     # submitted but not yet executed
    ALIVE = "alive"           # executed successfully, positive fitness
    DORMANT = "dormant"       # low fitness, not propagated
    EXTINCT = "extinct"       # fitness below extinction threshold
    MUTATED = "mutated"       # reproduced into one or more children


class FitnessSignal(BaseModel):
    """A fitness rating submitted by a node after executing a Spore."""

    node_id: str
    spore_id: str
    score: float                            # 0.0 – 1.0
    execution_time_ms: float
    output_hash: str                        # sha256(stdout)
    cpo_id: Optional[str] = None           # CPO proof of this execution
    rated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    notes: str = ""


class Spore(BaseModel):
    """
    The atomic unit of the Swarm — a verifiable, evolvable computation.

    A Spore is a CPO where execution is the content:
      code  →  BEE sandbox  →  stdout  →  SHA-256 + Ed25519  →  fitness

    Lineage tracks the genetic history: each mutation is a child Spore
    pointing to its parent, forming a directed acyclic ancestry graph.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    code: str                               # Python program to execute in BEE
    description: str = ""                  # human-readable purpose

    # Genetic lineage
    parent_id: Optional[str] = None        # None = primordial (no parent)
    generation: int = 0                    # 0 = seed, increments with mutations
    mutation_notes: str = ""               # what changed from parent

    # Fitness
    status: SporeStatus = SporeStatus.PROPOSED
    fitness: float = 0.0                   # aggregated score from all signals
    execution_count: int = 0
    fitness_signals: List[FitnessSignal] = Field(default_factory=list)

    # Proof trail — every execution produces a CPO
    cpo_ids: List[str] = Field(default_factory=list)
    content_hash: Optional[str] = None     # sha256 of canonical spore payload

    # Provenance
    created_by: str = ""                   # node_id of origin node
    born_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    last_executed_at: Optional[datetime] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)

    def update_fitness(self) -> None:
        """Recompute fitness from all signals (exponential recency weighting)."""
        if not self.fitness_signals:
            return
        signals = sorted(self.fitness_signals, key=lambda s: s.rated_at)
        weighted_sum = 0.0
        weight_total = 0.0
        decay = 0.9  # each older signal counts for 90% of the next
        for i, sig in enumerate(reversed(signals)):
            w = decay ** i
            weighted_sum += w * sig.score
            weight_total += w
        self.fitness = weighted_sum / weight_total if weight_total > 0 else 0.0


class SwarmStats(BaseModel):
    """Aggregate statistics for the local swarm population."""

    total_spores: int = 0
    alive_count: int = 0
    dormant_count: int = 0
    extinct_count: int = 0
    total_executions: int = 0
    mean_fitness: float = 0.0
    max_fitness: float = 0.0
    max_generation: int = 0
    top_spore_ids: List[str] = Field(default_factory=list)
