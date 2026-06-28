"""SIOS v1 pipeline — load → detect → report.

Standalone module used by the CLI. Does NOT require the FastAPI server.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from sios.core.ingestion import from_csv, from_json
from sios.core.models import Finding
from sios.value_engine.engine import ValueEngine

_engine = ValueEngine()


@dataclass
class AuditResult:
    findings: List[Finding] = field(default_factory=list)
    estimated_savings: float = 0.0
    currency: str = "EUR"
    dataset_rows: int = 0
    summary: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "dataset_rows": self.dataset_rows,
            "findings": [
                {
                    "type": f.type.value,
                    "title": f.title,
                    "vendor": next(
                        (e.split("=", 1)[1] for e in f.evidence if e.startswith("vendor=")),
                        "",
                    ),
                    "estimated_amount": f.estimated_amount,
                    "confidence": round(f.confidence, 2),
                    "currency": f.currency,
                    "description": f.description,
                }
                for f in self.findings
            ],
            "estimated_savings": round(self.estimated_savings, 2),
            "currency": self.currency,
            "summary": self.summary,
        }


def run_file(path: str | Path) -> AuditResult:
    """Run a full audit on a CSV or JSON file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    raw = p.read_bytes()
    suffix = p.suffix.lower()

    if suffix == ".csv":
        transactions = from_csv(raw, source=p.name)
    elif suffix == ".json":
        transactions = from_json(raw.decode(), source=p.name)
    else:
        raise ValueError(f"Unsupported file format: {suffix}. Use .csv or .json")

    if not transactions:
        return AuditResult()

    findings = _engine.run(transactions)
    summary = _engine.summary(findings)
    estimated = sum(f.estimated_amount for f in findings if f.estimated_amount)
    currency = findings[0].currency if findings else "EUR"

    return AuditResult(
        findings=findings,
        estimated_savings=estimated,
        currency=currency,
        dataset_rows=len(transactions),
        summary=summary,
    )
