"""SIOS — find hidden financial losses in your data. Proved, not predicted."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .pipeline import AuditResult, run_file

__version__ = "1.0.0"
__all__ = ["SIOS", "AuditResult", "__version__"]


class SIOS:
    """One-line API for financial loss detection.

    Example::

        from sios import SIOS

        agent = SIOS()
        result = agent.run("data/transactions.csv")

        print(result.estimated_savings)   # e.g. 1247.0
        for f in result.findings:
            print(f.type.value, f.title, f.estimated_amount)
    """

    def __init__(self, currency: str = "EUR") -> None:
        self.currency = currency

    def run(self, file: str | Path) -> AuditResult:
        """Run a full audit on a CSV or JSON file."""
        return run_file(file)

    def detect(self, file: str | Path) -> AuditResult:
        """Alias for run()."""
        return self.run(file)
