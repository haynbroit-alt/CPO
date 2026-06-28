"""FinanceAuditAgent — MVP agent: discovers financial savings from transaction data."""

from __future__ import annotations

from typing import List

from sios.agents.base import SIOSAgent
from sios.core.models import CanonicalTransaction, FindingType
from sios.discovery.models import Opportunity, OpportunityType
from sios.value_engine.engine import ValueEngine


_TYPE_MAP = {
    FindingType.DUPLICATE_PAYMENT: OpportunityType.DUPLICATE_PAYMENT,
    FindingType.UNUSED_SUBSCRIPTION: OpportunityType.UNUSED_SUBSCRIPTION,
    FindingType.COST_ANOMALY: OpportunityType.COST_ANOMALY,
    FindingType.CLOUD_WASTE: OpportunityType.CLOUD_WASTE,
    FindingType.TAX_CREDIT: OpportunityType.TAX_CREDIT,
    FindingType.PUBLIC_GRANT: OpportunityType.PUBLIC_GRANT,
}


class FinanceAuditAgent(SIOSAgent):
    """MVP agent: scans financial transactions and discovers saving opportunities.

    This is the first revenue-generating agent in SIOS One — it converts
    the Value Engine's Findings into unified Opportunities that flow through
    the Proof Engine and produce PVCs.
    """

    name = "finance_audit_agent"
    domain = "finance"

    def __init__(self) -> None:
        self._engine = ValueEngine()

    def discover(
        self,
        transactions: List[CanonicalTransaction] | None = None,
        **kwargs,
    ) -> List[Opportunity]:
        if not transactions:
            return []

        findings = self._engine.run(transactions)
        opportunities: List[Opportunity] = []
        for f in findings:
            opp = Opportunity(
                type=_TYPE_MAP.get(f.type, OpportunityType.FINANCIAL_SAVING),
                title=f.title,
                description=f.description,
                confidence=f.confidence,
                estimated_value=f.estimated_amount,
                currency=f.currency,
                evidence=f.evidence,
                entities=[e for ev in f.evidence for e in (ev.get("tags") or [])],
                recommended_actions=f.recommended_actions,
                discovery_engine=self.name,
                discovery_domain=self.domain,
                metadata={"finding_id": f.id, "detector": f.detector},
            )
            opportunities.append(opp)

        return opportunities

    def evaluate(self, opportunity: Opportunity) -> Opportunity:
        """Financial value score: confidence weighted by estimated value."""
        val = opportunity.estimated_value or 0
        value_factor = min(val / 5_000, 1.0)
        opportunity.value_score = round(
            0.6 * opportunity.confidence + 0.4 * value_factor, 3
        )
        return opportunity
