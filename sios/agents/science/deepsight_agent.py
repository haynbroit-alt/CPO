"""DeepSightAgent — discovers hidden knowledge connections and blind spots."""

from __future__ import annotations

from typing import List, Optional

from sios.agents.base import SIOSAgent
from sios.discovery.engine import DiscoveryEngine
from sios.discovery.models import Opportunity


class DeepSightAgent(SIOSAgent):
    """Science discovery agent — scans arXiv, PubMed, Wikipedia and reveals:

    - Cross-domain connections (concepts shared across disciplines)
    - Blind spots (under-researched concepts)
    - Emerging signals (concepts rising fast across multiple domains)

    It does not search for what you ask — it finds what nobody thought to look for.
    """

    name = "deepsight_agent"
    domain = "science"

    def __init__(self) -> None:
        self._engine = DiscoveryEngine()

    def discover(
        self,
        arxiv_categories: Optional[List[str]] = None,
        arxiv_max: int = 30,
        pubmed_query: str = "machine learning",
        pubmed_max: int = 20,
        wikipedia_topics: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Opportunity]:
        return self._engine.run(
            arxiv_categories=arxiv_categories or ["cs.AI", "q-bio.NC"],
            arxiv_max=arxiv_max,
            pubmed_query=pubmed_query,
            pubmed_max=pubmed_max,
            wikipedia_topics=wikipedia_topics or ["Artificial intelligence", "Neuroscience"],
        )
