"""Base Agent — the universal pipeline: Discover → Verify → Evaluate → Recommend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sios.discovery.models import Opportunity, OpportunityStatus


class SIOSAgent(ABC):
    """
    Every SIOS agent implements the four-phase pipeline:

    1. discover()   — find Opportunities from any source
    2. verify()     — attach a CPO proof (Proof Engine)
    3. evaluate()   — compute a Value Score (Value Engine)
    4. recommend()  — produce human-readable recommended actions

    Agents are domain-specialised (finance, science, business) but share
    this interface so the orchestration layer is uniform.
    """

    name: str = "base_agent"
    domain: str = "general"
    version: str = "0.1.0"

    # ── Phase 1: Discovery ───────────────────────────────────────────────────

    @abstractmethod
    def discover(self, **kwargs) -> List[Opportunity]:
        """Scan sources and return raw Opportunities."""
        ...

    # ── Phase 2: Verification (Proof Engine) ─────────────────────────────────

    def verify(
        self,
        opportunity: Opportunity,
        cpo_client: Optional[Any] = None,
    ) -> Opportunity:
        """Attach a CPO to the Opportunity (optional — requires a CPO node)."""
        if cpo_client is None:
            return opportunity
        try:
            code = (
                f"# SIOS Agent: {self.name}\n"
                f"# Opportunity: {opportunity.id}\n"
                f"confidence = {opportunity.confidence}\n"
                f"estimated_value = {opportunity.estimated_value!r}\n"
                f"entities = {opportunity.entities!r}\n"
                f"print(f'opportunity={opportunity.id} confidence={opportunity.confidence}')"
            )
            result = cpo_client.prove(
                claim=f"[{self.name}] {opportunity.title[:120]}",
                code=code,
                world="llm",
            )
            opportunity.cpo_id = result.get("cpo_id")
            opportunity.status = OpportunityStatus.PROVED
        except Exception:
            pass
        return opportunity

    # ── Phase 3: Evaluation (Value Engine) ───────────────────────────────────

    def evaluate(self, opportunity: Opportunity) -> Opportunity:
        """Compute a Value Score. Override for domain-specific scoring."""
        base = opportunity.confidence
        if opportunity.estimated_value is not None and opportunity.estimated_value > 0:
            # Financial opportunities get a boost proportional to amount
            value_factor = min(opportunity.estimated_value / 10_000, 1.0)
            base = min(base + 0.2 * value_factor, 1.0)
        opportunity.value_score = round(base, 3)
        opportunity.status = OpportunityStatus.EVALUATED
        return opportunity

    # ── Phase 4: Recommendations ─────────────────────────────────────────────

    def recommend(self, opportunity: Opportunity) -> List[str]:
        """Return recommended actions. Override for domain-specific logic."""
        return opportunity.recommended_actions

    # ── Full pipeline ─────────────────────────────────────────────────────────

    def run(self, cpo_client: Optional[Any] = None, **discover_kwargs) -> List[Opportunity]:
        """Execute the full Discover → Verify → Evaluate pipeline."""
        opportunities = self.discover(**discover_kwargs)
        results = []
        for opp in opportunities:
            opp.discovery_engine = self.name
            opp.discovery_domain = self.domain
            opp = self.verify(opp, cpo_client=cpo_client)
            opp = self.evaluate(opp)
            results.append(opp)
        return sorted(results, key=lambda o: o.value_score or 0, reverse=True)

    def describe(self) -> Dict:
        return {
            "name": self.name,
            "domain": self.domain,
            "version": self.version,
            "description": self.__class__.__doc__ or "",
        }
