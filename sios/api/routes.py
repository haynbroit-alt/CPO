"""SIOS FastAPI routes — /ingest, /detect, /discover, /finding, /pvc, /recover, /swarm."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from sios.core.ingestion import from_csv, from_json
from sios.core.models import (
    CanonicalTransaction,
    Finding,
    FindingStatus,
    PVC,
    RecoveryProof,
)
from sios.discovery.engine import DiscoveryEngine
from sios.discovery.models import Opportunity
from sios.swarm.models import FitnessSignal, Spore as SwarmSpore
from sios.swarm.node import SwarmNode
from sios.value_engine.engine import ValueEngine

router = APIRouter(prefix="/sios", tags=["SIOS"])

# ---------------------------------------------------------------------------
# In-memory stores (replace with PostgreSQL in production)
# ---------------------------------------------------------------------------
_transactions: Dict[str, CanonicalTransaction] = {}
_findings: Dict[str, Finding] = {}
_pvcs: Dict[str, PVC] = {}
_opportunities: Dict[str, Opportunity] = {}
_discovery_engine = DiscoveryEngine()
_engine = ValueEngine()


def _swarm() -> SwarmNode:
    """Lazily initialise the local SwarmNode (singleton per process)."""
    global _swarm_node
    if _swarm_node is None:
        node_id = os.environ.get("SIOS_NODE_ID", f"node-{uuid.uuid4().hex[:8]}")
        llm_available = bool(os.environ.get("ANTHROPIC_API_KEY"))
        _swarm_node = SwarmNode(node_id=node_id, llm_available=llm_available)
    return _swarm_node


_swarm_node: Optional[SwarmNode] = None


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    source: str = "json"
    data: List[Dict[str, Any]]
    column_map: Optional[Dict[str, str]] = None


class DetectRequest(BaseModel):
    transaction_ids: Optional[List[str]] = None  # None = use all ingested


class RecoverRequest(BaseModel):
    finding_id: str
    recovered_amount: float
    currency: str = "EUR"
    document_refs: List[str] = []
    data_refs: List[str] = []
    beneficiary: str
    cpo_id: Optional[str] = None
    notes: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/ingest", status_code=201)
def ingest(req: IngestRequest) -> Dict:
    """Ingest a JSON array of transactions into the canonical data model."""
    raw_json = json.dumps(req.data)
    txns = from_json(raw_json, source=req.source, column_map=req.column_map)
    for t in txns:
        _transactions[t.id] = t
    return {
        "status": "ingested",
        "count": len(txns),
        "transaction_ids": [t.id for t in txns],
    }


@router.post("/ingest/csv", status_code=201)
async def ingest_csv(file: UploadFile = File(...)) -> Dict:
    """Ingest a CSV file upload."""
    content = await file.read()
    txns = from_csv(content, source=file.filename or "csv")
    for t in txns:
        _transactions[t.id] = t
    return {
        "status": "ingested",
        "count": len(txns),
        "transaction_ids": [t.id for t in txns],
    }


@router.post("/normalize")
def normalize(transaction_ids: Optional[List[str]] = None) -> Dict:
    """Return canonical form of ingested transactions."""
    txns = _get_transactions(transaction_ids)
    return {
        "count": len(txns),
        "transactions": [t.model_dump() for t in txns],
    }


@router.post("/detect", status_code=201)
def detect(req: DetectRequest) -> Dict:
    """Run all Value Engine detectors and store resulting Findings."""
    txns = _get_transactions(req.transaction_ids)
    if not txns:
        raise HTTPException(status_code=422, detail="No transactions available. Ingest first.")

    new_findings = _engine.run(txns)
    for f in new_findings:
        _findings[f.id] = f

    summary = _engine.summary(new_findings)
    return {
        "status": "ok",
        "new_findings": len(new_findings),
        "finding_ids": [f.id for f in new_findings],
        "summary": summary,
    }


@router.get("/finding/{finding_id}")
def get_finding(finding_id: str) -> Dict:
    """Retrieve a stored Finding by ID."""
    f = _findings.get(finding_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return f.model_dump()


@router.get("/findings")
def list_findings(status: Optional[str] = None, finding_type: Optional[str] = None) -> List[Dict]:
    """List all stored Findings, optionally filtered by status or type."""
    results = list(_findings.values())
    if status:
        results = [f for f in results if f.status.value == status]
    if finding_type:
        results = [f for f in results if f.type.value == finding_type]
    results.sort(key=lambda f: f.confidence, reverse=True)
    return [f.model_dump() for f in results]


@router.post("/recover", status_code=201)
def recover(req: RecoverRequest) -> Dict:
    """Record that a Finding was recovered — creates a PVC."""
    finding = _findings.get(req.finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found")

    recovery = RecoveryProof(
        document_refs=req.document_refs,
        data_refs=req.data_refs,
        recovered_amount=req.recovered_amount,
        recovered_at=datetime.now(tz=timezone.utc),
        notes=req.notes,
    )
    pvc = PVC(
        finding_id=req.finding_id,
        cpo_id=req.cpo_id,
        recovery_proof=recovery,
        beneficiary=req.beneficiary,
    )
    _pvcs[pvc.id] = pvc

    finding.status = FindingStatus.RECOVERED
    _findings[finding.id] = finding

    return {
        "status": "recovered",
        "pvc_id": pvc.id,
        "finding_id": req.finding_id,
        "recovered_amount": req.recovered_amount,
        "created_at": pvc.created_at.isoformat(),
    }


@router.get("/pvc/{pvc_id}")
def get_pvc(pvc_id: str) -> Dict:
    """Retrieve a Proof of Value Creation by ID."""
    pvc = _pvcs.get(pvc_id)
    if pvc is None:
        raise HTTPException(status_code=404, detail="PVC not found")
    return pvc.model_dump()


@router.get("/leaderboard")
def leaderboard() -> List[Dict]:
    """Return PVCs ranked by recovered amount."""
    pvcs = sorted(_pvcs.values(), key=lambda p: p.recovery_proof.recovered_amount, reverse=True)
    return [
        {
            "pvc_id": p.id,
            "finding_id": p.finding_id,
            "beneficiary": p.beneficiary,
            "recovered_amount": p.recovery_proof.recovered_amount,
            "created_at": p.created_at.isoformat(),
            "cpo_id": p.cpo_id,
        }
        for p in pvcs
    ]


# ---------------------------------------------------------------------------
# Discovery Engine routes
# ---------------------------------------------------------------------------

class DiscoverRequest(BaseModel):
    arxiv_categories: Optional[List[str]] = None
    arxiv_max: int = 20
    pubmed_query: str = "machine learning"
    pubmed_max: int = 15
    wikipedia_topics: Optional[List[str]] = None


@router.post("/discover", status_code=201)
def discover(req: DiscoverRequest) -> Dict:
    """Run the Discovery Engine (DeepSight) and store resulting Opportunities."""
    opps = _discovery_engine.run(
        arxiv_categories=req.arxiv_categories,
        arxiv_max=req.arxiv_max,
        pubmed_query=req.pubmed_query,
        pubmed_max=req.pubmed_max,
        wikipedia_topics=req.wikipedia_topics,
    )
    for o in opps:
        _opportunities[o.id] = o

    summary = _discovery_engine.summary(opps)
    return {
        "status": "ok",
        "new_opportunities": len(opps),
        "opportunity_ids": [o.id for o in opps],
        "summary": summary,
    }


@router.get("/opportunity/{opp_id}")
def get_opportunity(opp_id: str) -> Dict:
    """Retrieve a stored Opportunity by ID."""
    o = _opportunities.get(opp_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return o.model_dump()


@router.get("/opportunities")
def list_opportunities(
    domain: Optional[str] = None,
    opp_type: Optional[str] = None,
    min_confidence: float = 0.0,
) -> List[Dict]:
    """List all stored Opportunities, optionally filtered."""
    results = list(_opportunities.values())
    if domain:
        results = [o for o in results if o.discovery_domain == domain]
    if opp_type:
        results = [o for o in results if o.type.value == opp_type]
    results = [o for o in results if o.confidence >= min_confidence]
    results.sort(key=lambda o: o.confidence, reverse=True)
    return [o.model_dump() for o in results]


# ---------------------------------------------------------------------------
# Swarm routes
# ---------------------------------------------------------------------------

class SporeSubmitRequest(BaseModel):
    code: str
    description: str = ""
    parent_id: Optional[str] = None
    generation: int = 0
    mutation_notes: str = ""
    metadata: Dict[str, Any] = {}


class RateSporeRequest(BaseModel):
    score: float                    # 0.0 – 1.0
    execution_time_ms: float = 0.0
    output_hash: str = ""
    notes: str = ""


class EvolveRequest(BaseModel):
    pass  # no parameters for now; reserved for future strategy overrides


@router.post("/spore", status_code=201)
def submit_spore(req: SporeSubmitRequest) -> Dict:
    """Submit a new Spore to the local swarm."""
    spore = SwarmSpore(
        code=req.code,
        description=req.description,
        parent_id=req.parent_id,
        generation=req.generation,
        mutation_notes=req.mutation_notes,
        metadata=req.metadata,
    )
    node = _swarm()
    accepted = node.ingest(spore)
    return {
        "status": "accepted" if accepted else "duplicate",
        "spore_id": spore.id,
        "generation": spore.generation,
    }


@router.post("/spore/{spore_id}/execute", status_code=201)
def execute_spore(spore_id: str) -> Dict:
    """Execute a Spore in the BEE sandbox and return its fitness signal."""
    node = _swarm()
    signal = node.execute(spore_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Spore not found")
    spore = node.get(spore_id)
    return {
        "spore_id": spore_id,
        "status": spore.status.value if spore else "unknown",
        "fitness": spore.fitness if spore else 0.0,
        "signal": signal.model_dump(),
    }


@router.post("/spore/{spore_id}/rate", status_code=201)
def rate_spore(spore_id: str, req: RateSporeRequest) -> Dict:
    """Submit an external fitness signal for a Spore."""
    node = _swarm()
    spore = node.get(spore_id)
    if spore is None:
        raise HTTPException(status_code=404, detail="Spore not found")

    signal = FitnessSignal(
        node_id=f"external-{uuid.uuid4().hex[:8]}",
        spore_id=spore_id,
        score=max(0.0, min(1.0, req.score)),
        execution_time_ms=req.execution_time_ms,
        output_hash=req.output_hash or f"external-{uuid.uuid4().hex}",
        notes=req.notes,
    )
    spore.fitness_signals.append(signal)
    spore.update_fitness()

    return {
        "spore_id": spore_id,
        "fitness": round(spore.fitness, 3),
        "signal_count": len(spore.fitness_signals),
    }


@router.get("/spore/{spore_id}")
def get_spore(spore_id: str) -> Dict:
    """Retrieve a Spore by ID."""
    spore = _swarm().get(spore_id)
    if spore is None:
        raise HTTPException(status_code=404, detail="Spore not found")
    return spore.model_dump()


@router.get("/swarm/stats")
def swarm_stats() -> Dict:
    """Return aggregate statistics for the local swarm population."""
    return _swarm().stats().model_dump()


@router.get("/swarm/top")
def swarm_top(n: int = 10) -> List[Dict]:
    """Return the n highest-fitness alive Spores."""
    return [s.model_dump() for s in _swarm().top_spores(n)]


@router.post("/swarm/evolve", status_code=201)
def swarm_evolve(_req: EvolveRequest = EvolveRequest()) -> Dict:
    """Trigger one evolution cycle — select, mutate, produce children."""
    node = _swarm()
    children = node.evolve()
    return {
        "status": "evolved",
        "new_children": len(children),
        "child_ids": [c.id for c in children],
        "stats": node.stats().model_dump(),
    }


@router.get("/swarm/leaderboard")
def swarm_leaderboard() -> List[Dict]:
    """All Spores ranked by fitness, with lineage information."""
    spores = sorted(_swarm().all(), key=lambda s: s.fitness, reverse=True)
    return [
        {
            "rank": i + 1,
            "spore_id": s.id,
            "fitness": round(s.fitness, 3),
            "status": s.status.value,
            "generation": s.generation,
            "parent_id": s.parent_id,
            "execution_count": s.execution_count,
            "description": s.description,
        }
        for i, s in enumerate(spores)
    ]


@router.delete("/swarm", status_code=200)
def swarm_purge() -> Dict:
    """Consent revocation — remove all Spores from this node."""
    n = _swarm().purge()
    return {"status": "purged", "removed": n}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_transactions(ids: Optional[List[str]]) -> List[CanonicalTransaction]:
    if ids is None:
        return list(_transactions.values())
    return [_transactions[i] for i in ids if i in _transactions]
