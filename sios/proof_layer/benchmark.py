"""SIOS Proof Layer — Sector benchmark computation."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from sios.proof_layer.seed import get_seed_audits


def _compute_sector(sector: str) -> Optional[Dict[str, Any]]:
    audits = [a for a in get_seed_audits() if a.sector == sector and a.is_public]
    if not audits:
        return None

    txn_counts = [a.transactions_analyzed for a in audits]
    anomaly_counts = [a.anomalies_detected for a in audits]
    savings = [a.confirmed_savings_eur or a.estimated_savings_eur for a in audits]

    # Anomaly rate = anomalies / transactions * 100
    rates = [an / tx * 100 for an, tx in zip(anomaly_counts, txn_counts)]
    avg_rate = round(sum(rates) / len(rates), 2) if rates else 0

    avg_savings = round(sum(savings) / len(savings)) if savings else 0
    max_savings = max(savings) if savings else 0

    # Most common anomaly types across sector
    type_counter: Counter = Counter()
    vendor_counter: Counter = Counter()
    for a in audits:
        for an in a.anomalies:
            type_counter[an.type.value] += 1
            vendor_counter[an.vendor] += 1

    verified_count = sum(1 for a in audits if a.verification.client_approved)

    return {
        "sector": sector,
        "audit_count": len(audits),
        "verified_count": verified_count,
        "avg_anomaly_rate_pct": avg_rate,
        "avg_savings_eur": avg_savings,
        "max_savings_eur": round(max_savings),
        "avg_transactions": round(sum(txn_counts) / len(txn_counts)),
        "top_anomaly_types": [t for t, _ in type_counter.most_common(3)],
        "top_vendors": [v for v, _ in vendor_counter.most_common(3)],
    }


def all_sector_benchmarks() -> List[Dict[str, Any]]:
    sectors = list({a.sector for a in get_seed_audits()})
    result = []
    for s in sorted(sectors):
        b = _compute_sector(s)
        if b:
            result.append(b)
    return result


def sector_benchmark(sector: str) -> Optional[Dict[str, Any]]:
    return _compute_sector(sector)


def compare_to_sector(sector: str, user_anomaly_rate_pct: float, user_transactions: int) -> Dict[str, Any]:
    """Compare a user's anomaly rate against sector average and estimate savings potential."""
    bench = _compute_sector(sector)
    if not bench:
        return {"error": f"No benchmark data for sector: {sector}"}

    delta_pct = round(user_anomaly_rate_pct - bench["avg_anomaly_rate_pct"], 2)
    percentile = _estimate_percentile(sector, user_anomaly_rate_pct)

    # Savings estimate: scale sector avg by transaction ratio vs. sector avg
    scale = user_transactions / bench["avg_transactions"] if bench["avg_transactions"] else 1.0
    est_savings_low = round(bench["avg_savings_eur"] * scale * 0.7)
    est_savings_high = round(bench["avg_savings_eur"] * scale * 1.4)

    risk_level = "elevated" if user_anomaly_rate_pct > bench["avg_anomaly_rate_pct"] else "normal"
    if user_anomaly_rate_pct > bench["avg_anomaly_rate_pct"] * 1.5:
        risk_level = "high"

    return {
        "sector": sector,
        "user_anomaly_rate_pct": user_anomaly_rate_pct,
        "sector_avg_rate_pct": bench["avg_anomaly_rate_pct"],
        "delta_pct": delta_pct,
        "percentile": percentile,
        "risk_level": risk_level,
        "estimated_savings_low": est_savings_low,
        "estimated_savings_high": est_savings_high,
        "top_anomaly_types": bench["top_anomaly_types"],
        "audit_count_in_sector": bench["audit_count"],
    }


def _estimate_percentile(sector: str, rate: float) -> int:
    """Rough percentile estimate — what % of sector companies have a LOWER anomaly rate."""
    audits = [a for a in get_seed_audits() if a.sector == sector]
    if not audits:
        return 50
    rates = sorted(a.anomalies_detected / a.transactions_analyzed * 100 for a in audits)
    below = sum(1 for r in rates if r < rate)
    return round(below / len(rates) * 100)
