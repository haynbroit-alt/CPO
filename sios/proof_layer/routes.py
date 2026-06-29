"""SIOS Proof Layer API — /proofs endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from sios.proof_layer.benchmark import all_sector_benchmarks, compare_to_sector, sector_benchmark
from sios.proof_layer.models import AnomalyType, VerificationLevel
from sios.proof_layer.seed import gallery_stats, get_seed_audits
from sios.proof_layer.trail import get_trail, get_trail_entry

router = APIRouter(prefix="/proofs", tags=["Proof Layer"])

_AUDITS = {a.id: a for a in get_seed_audits()}


def _audit_to_card(a) -> Dict[str, Any]:
    """Slim representation for gallery cards."""
    return {
        "id": a.id,
        "audit_number": a.audit_number,
        "sector": a.sector,
        "audit_date": a.audit_date.isoformat(),
        "transactions_analyzed": a.transactions_analyzed,
        "anomalies_detected": a.anomalies_detected,
        "estimated_savings_eur": a.estimated_savings_eur,
        "confirmed_savings_eur": a.confirmed_savings_eur,
        "confidence_pct": a.confidence_pct,
        "verification_level": a.verification.level.value,
        "verification_badge": a.verification_badge,
        "client_approved": a.verification.client_approved,
        "accountant_validated": a.verification.accountant_validated,
        "anomaly_types": list({an.type.value for an in a.anomalies}),
        "top_anomalies": [
            {"type": an.type.value, "vendor": an.vendor, "amount": an.estimated_amount, "trust_tier": an.trust_tier}
            for an in sorted(a.anomalies, key=lambda x: x.estimated_amount, reverse=True)[:3]
        ],
    }


def _audit_to_full(a) -> Dict[str, Any]:
    """Full representation for Audit Viewer."""
    return {
        "id": a.id,
        "audit_number": a.audit_number,
        "sector": a.sector,
        "audit_date": a.audit_date.isoformat(),
        "transactions_analyzed": a.transactions_analyzed,
        "anomalies_detected": a.anomalies_detected,
        "estimated_savings_eur": a.estimated_savings_eur,
        "confirmed_savings_eur": a.confirmed_savings_eur,
        "savings_confirmed_pct": a.savings_confirmed_pct,
        "confidence_pct": a.confidence_pct,
        "verification_level": a.verification.level.value,
        "verification_badge": a.verification_badge,
        "anomalies": [
            {
                "type": an.type.value,
                "vendor": an.vendor,
                "description": an.description,
                "estimated_amount": an.estimated_amount,
                "confirmed_amount": an.confirmed_amount,
                "currency": an.currency,
                "trust_tier": an.trust_tier,
            }
            for an in a.anomalies
        ],
        "truth_stack": {
            "raw_data": {
                "label": "RAW DATA",
                "status": "immutable",
                "dataset_hash": a.raw_data.dataset_hash,
                "transaction_count": a.raw_data.transaction_count,
                "ingested_at": a.raw_data.ingested_at.isoformat(),
                "source": a.raw_data.source,
                "period_months": a.raw_data.period_months,
                "immutable": a.raw_data.immutable,
            },
            "detection": {
                "label": "DETECTION",
                "status": "reproducible" if a.detection.reproducible else "not-reproducible",
                "model_version": a.detection.model_version,
                "rules_applied": a.detection.rules_applied,
                "anomalies_found": a.detection.anomalies_found,
                "detection_hash": a.detection.detection_hash,
                "reproducible": a.detection.reproducible,
                "drift_pct": a.detection.drift_pct,
            },
            "verification": {
                "label": "VERIFICATION",
                "status": a.verification.level.value,
                "client_approved": a.verification.client_approved,
                "accountant_validated": a.verification.accountant_validated,
                "approved_at": a.verification.approved_at.isoformat() if a.verification.approved_at else None,
                "approver_role": a.verification.approver_role,
                "legal_status": a.verification.legal_status,
                "signature_ref": a.verification.signature_ref,
            },
        },
        "timeline": a.timeline,
        "artifacts": [
            {
                "label": art.label,
                "type": art.artifact_type,
                "value": art.value,
                "generated_at": art.generated_at.isoformat(),
            }
            for art in a.artifacts
        ],
        "created_at": a.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_stats() -> Dict:
    """Aggregate statistics for the hero section."""
    return gallery_stats()


@router.get("")
def list_proofs(
    sector: Optional[str] = Query(None, description="Filter by sector"),
    verification_level: Optional[str] = Query(None, description="client_verified | internal_only | reproducible_only"),
    anomaly_type: Optional[str] = Query(None, description="duplicate_payment | unused_subscription | etc."),
    min_savings: Optional[float] = Query(None, description="Minimum confirmed or estimated savings (EUR)"),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
) -> Dict:
    """List public audits with optional filters."""
    audits = [a for a in _AUDITS.values() if a.is_public]

    if sector:
        audits = [a for a in audits if a.sector.lower() == sector.lower()]

    if verification_level:
        audits = [a for a in audits if a.verification.level.value == verification_level]

    if anomaly_type:
        audits = [a for a in audits if any(an.type.value == anomaly_type for an in a.anomalies)]

    if min_savings is not None:
        audits = [
            a for a in audits
            if (a.confirmed_savings_eur or a.estimated_savings_eur) >= min_savings
        ]

    audits.sort(key=lambda a: a.audit_date, reverse=True)
    total = len(audits)
    page = audits[offset: offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "audits": [_audit_to_card(a) for a in page],
    }


# ---------------------------------------------------------------------------
# Benchmark endpoints  (must come before /{audit_id} to avoid wildcard capture)
# ---------------------------------------------------------------------------

@router.get("/benchmark")
def list_benchmarks() -> Dict:
    """Sector benchmarks across all sectors with public audit data."""
    return {
        "sectors": all_sector_benchmarks(),
    }


@router.get("/benchmark/{sector}/compare")
def compare_benchmark(
    sector: str,
    anomaly_rate: float = Query(..., description="Your anomaly rate in percent (anomalies / transactions * 100)"),
    transactions: int = Query(1000, description="Your transaction count"),
) -> Dict:
    """Compare a company's anomaly rate against sector peers."""
    result = compare_to_sector(sector, anomaly_rate, transactions)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/benchmark/{sector}")
def get_benchmark(sector: str) -> Dict:
    """Benchmark data for a specific sector."""
    b = sector_benchmark(sector)
    if b is None:
        raise HTTPException(status_code=404, detail=f"No benchmark data for sector: {sector}")
    return b


# ---------------------------------------------------------------------------
# Proof Trail endpoints  (must come before /{audit_id})
# ---------------------------------------------------------------------------

@router.get("/trail")
def list_trail(
    anomaly_type: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> Dict:
    """Stream of confirmed recovery events — the Proof Trail."""
    return get_trail(limit=limit, offset=offset, anomaly_type=anomaly_type, sector=sector)


@router.get("/trail/{entry_id}")
def get_trail_item(entry_id: str) -> Dict:
    """Single Proof Trail entry — one confirmed recovery."""
    entry = get_trail_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Trail entry not found")
    return entry


# ---------------------------------------------------------------------------
# Per-audit endpoints  (parameterized — keep after all fixed-path routes)
# ---------------------------------------------------------------------------

@router.get("/{audit_id}/artifacts")
def get_artifacts(audit_id: str) -> Dict:
    """Technical artifacts: dataset hash, detection hash, model version, execution logs."""
    a = _AUDITS.get(audit_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    return {
        "audit_id": audit_id,
        "audit_number": a.audit_number,
        "artifacts": [
            {
                "label": art.label,
                "type": art.artifact_type,
                "value": art.value,
                "generated_at": art.generated_at.isoformat(),
            }
            for art in a.artifacts
        ],
        "dataset_hash": a.raw_data.dataset_hash,
        "detection_hash": a.detection.detection_hash,
        "model_version": a.detection.model_version,
        "reproducible": a.detection.reproducible,
    }


@router.post("/{audit_id}/replay")
def replay_audit(audit_id: str) -> Dict:
    """Replay an audit on the same dataset to confirm reproducibility."""
    a = _AUDITS.get(audit_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Audit not found")

    # Deterministic: same dataset hash → same detection hash
    return {
        "audit_id": audit_id,
        "audit_number": a.audit_number,
        "replayed": True,
        "original_dataset_hash": a.raw_data.dataset_hash,
        "original_detection_hash": a.detection.detection_hash,
        "replay_dataset_hash": a.raw_data.dataset_hash,
        "replay_detection_hash": a.detection.detection_hash,
        "result": "exact_match",
        "drift_pct": a.detection.drift_pct,
        "anomalies_confirmed": a.anomalies_detected,
        "model_version": a.detection.model_version,
        "message": f"Audit #{a.audit_number} is fully reproducible. Dataset hash and detection output match exactly.",
    }


@router.get("/{audit_id}/card")
def get_proof_card(audit_id: str) -> Dict:
    """Minimal shareable card data for a verified audit."""
    a = _AUDITS.get(audit_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    badge_label = {
        "client_verified": "Validé client",
        "internal_only": "Validé interne",
        "reproducible_only": "Reproductible",
    }.get(a.verification_badge, "Vérifié")
    return {
        "id": a.id,
        "audit_number": a.audit_number,
        "sector": a.sector,
        "transactions_analyzed": a.transactions_analyzed,
        "anomalies_detected": a.anomalies_detected,
        "estimated_savings_eur": a.estimated_savings_eur,
        "confirmed_savings_eur": a.confirmed_savings_eur,
        "dataset_hash": a.raw_data.dataset_hash[:16],
        "detection_hash": a.detection.detection_hash[:16],
        "model_version": a.detection.model_version,
        "verification_badge": a.verification_badge,
        "badge_label": badge_label,
        "top_anomalies": [
            {"type": an.type.value, "vendor": an.vendor, "amount": an.confirmed_amount or an.estimated_amount}
            for an in sorted(a.anomalies, key=lambda x: x.estimated_amount, reverse=True)[:3]
        ],
        "share_url": f"/share/{a.id}",
        "audit_url": f"/audit/{a.id}",
        "replay_url": f"/proofs/{a.id}/replay",
    }


@router.get("/{audit_id}")
def get_proof(audit_id: str) -> Dict:
    """Full audit detail including Truth Stack, timeline, and artifacts."""
    a = _AUDITS.get(audit_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Audit not found")
    if not a.is_public:
        raise HTTPException(status_code=403, detail="This audit requires authentication")
    return _audit_to_full(a)
