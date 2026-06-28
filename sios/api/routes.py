"""SIOS FastAPI routes — /ingest, /detect, /finding, /pvc, /recover."""

from __future__ import annotations

import json
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
from sios.value_engine.engine import ValueEngine

router = APIRouter(prefix="/sios", tags=["SIOS"])

# ---------------------------------------------------------------------------
# In-memory stores (replace with PostgreSQL in production)
# ---------------------------------------------------------------------------
_transactions: Dict[str, CanonicalTransaction] = {}
_findings: Dict[str, Finding] = {}
_pvcs: Dict[str, PVC] = {}
_engine = ValueEngine()


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
# Helpers
# ---------------------------------------------------------------------------

def _get_transactions(ids: Optional[List[str]]) -> List[CanonicalTransaction]:
    if ids is None:
        return list(_transactions.values())
    return [_transactions[i] for i in ids if i in _transactions]
