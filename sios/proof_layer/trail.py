"""SIOS Proof Layer — Proof Trail: confirmed recovery events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sios.proof_layer.seed import get_seed_audits

_ANOMALY_LABELS = {
    "duplicate_payment": "Doublon de paiement",
    "unused_subscription": "Abonnement inutilisé",
    "unused_license": "Licence inutilisée",
    "cloud_waste": "Cloud waste",
    "cost_anomaly": "Anomalie de coût",
    "telecom_overcharge": "Surcharge télécom",
    "renegotiable_contract": "Contrat renégociable",
}


def _build_trail() -> List[Dict[str, Any]]:
    """Extract one trail entry per confirmed anomaly (confirmed_amount set and > 0)."""
    entries = []
    for audit in get_seed_audits():
        if not audit.verification.client_approved and not audit.verification.accountant_validated:
            continue

        # Use the timeline recovery step date if available
        recovery_date = audit.audit_date
        for step in audit.timeline:
            if step.get("step") == 4:
                try:
                    recovery_date = datetime.fromisoformat(step["date"])
                except Exception:
                    pass
                break

        for anomaly in audit.anomalies:
            if anomaly.confirmed_amount is None or anomaly.confirmed_amount <= 0:
                continue

            entry_id = f"trail-{audit.audit_number}-{anomaly.type.value[:4]}-{anomaly.vendor[:4].lower()}"
            entries.append({
                "id": entry_id,
                "audit_id": audit.id,
                "audit_number": audit.audit_number,
                "sector": audit.sector,
                "anomaly_type": anomaly.type.value,
                "anomaly_label": _ANOMALY_LABELS.get(anomaly.type.value, anomaly.type.value),
                "vendor": anomaly.vendor,
                "confirmed_amount": anomaly.confirmed_amount,
                "currency": anomaly.currency,
                "trust_tier": anomaly.trust_tier,
                "recovered_at": recovery_date.isoformat(),
                "dataset_hash": audit.raw_data.dataset_hash[:16],
                "verification_badge": audit.verification_badge,
                "headline": _headline(anomaly.confirmed_amount, anomaly.type.value, anomaly.vendor, audit.sector),
            })

    entries.sort(key=lambda e: e["recovered_at"], reverse=True)
    return entries


def _headline(amount: float, anomaly_type: str, vendor: str, sector: str) -> str:
    label = _ANOMALY_LABELS.get(anomaly_type, anomaly_type)
    amt = f"{int(amount):,}".replace(",", " ")
    return f"Une entreprise {sector} a récupéré {amt} € — {label} ({vendor})"


_TRAIL: List[Dict[str, Any]] = _build_trail()


def get_trail(limit: int = 50, offset: int = 0, anomaly_type: Optional[str] = None, sector: Optional[str] = None) -> Dict[str, Any]:
    entries = _TRAIL

    if anomaly_type:
        entries = [e for e in entries if e["anomaly_type"] == anomaly_type]
    if sector:
        entries = [e for e in entries if e["sector"].lower() == sector.lower()]

    total = len(entries)
    page = entries[offset: offset + limit]

    total_recovered = sum(e["confirmed_amount"] for e in _TRAIL)

    return {
        "total": total,
        "total_recovered_eur": round(total_recovered),
        "offset": offset,
        "limit": limit,
        "entries": page,
    }


def get_trail_entry(entry_id: str) -> Optional[Dict[str, Any]]:
    for e in _TRAIL:
        if e["id"] == entry_id:
            return e
    return None
