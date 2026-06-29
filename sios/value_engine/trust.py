"""Trust Score Engine — anti-hallucination layer for financial findings.

Rules:
  - LOW  (0–39):  signal only, no € amounts
  - MEDIUM (40–69): range estimate
  - HIGH (70–100): quantified estimate
"""

from __future__ import annotations

from typing import Dict


def trust_score(
    transaction_count: int,
    signal_strength: float,
    coverage_ratio: float,
) -> int:
    """Compute a 0–100 trust score for a finding group."""
    score = 0

    if transaction_count < 20:
        score -= 40
    elif transaction_count < 100:
        score += 10
    else:
        score += 30

    if signal_strength > 0.7:
        score += 30
    elif signal_strength > 0.4:
        score += 10
    else:
        score -= 20

    if coverage_ratio < 0.3:
        score -= 30

    # Boost for solid evidence even with small datasets
    if transaction_count >= 6 and signal_strength > 0.6:
        score += 15

    return max(0, min(100, score + 50))  # base 50 so average data scores MEDIUM


def trust_tier(score: int) -> str:
    if score < 40:
        return "LOW"
    elif score < 70:
        return "MEDIUM"
    return "HIGH"


def estimate_range(
    observed_total: float,
    transaction_count: int,
    months_coverage: float,
) -> Dict[str, float]:
    """
    Conservative range estimate — never extrapolates beyond observed data
    without a frequency anchor.
    """
    if months_coverage <= 0:
        months_coverage = 1.0

    frequency_factor = min(transaction_count / 12.0, 1.0)
    # Inefficiency ratio: how much of observed spend is likely recoverable
    duplication_risk = 0.10 + frequency_factor * 0.40

    return {
        "low": round(observed_total * duplication_risk * 0.5, 2),
        "mid": round(observed_total * duplication_risk, 2),
        "high": round(observed_total * duplication_risk * 1.3, 2),
    }


def signal_consistency(amounts: list[float]) -> float:
    """Return 0.0–1.0 — how consistent is the pattern (1.0 = identical amounts)."""
    if not amounts or len(amounts) < 2:
        return 0.5
    avg = sum(amounts) / len(amounts)
    if avg == 0:
        return 0.5
    variance = sum((a - avg) ** 2 for a in amounts) / len(amounts)
    cv = (variance ** 0.5) / avg  # coefficient of variation
    return max(0.0, min(1.0, 1.0 - cv))
