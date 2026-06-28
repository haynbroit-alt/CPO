"""Discovery Engine — orchestrates scanners and analyzers into Opportunities."""

from __future__ import annotations

from typing import Dict, List, Optional

from .analyzers import (
    detect_blind_spots,
    detect_emerging_signals,
    find_cross_domain_connections,
)
from .models import Opportunity
from .scanners.arxiv import ArxivScanner
from .scanners.base import BaseScanner, RawDocument
from .scanners.pubmed import PubMedScanner
from .scanners.wikipedia import WikipediaScanner


class DiscoveryEngine:
    """Scan multiple knowledge sources, analyze, and return Opportunities.

    Example::

        engine = DiscoveryEngine()
        opportunities = engine.run(
            arxiv_categories=["cs.AI", "q-bio.NC"],
            pubmed_query="neural plasticity",
            wikipedia_topics=["Deep learning", "Neuroplasticity"],
        )
        for opp in opportunities:
            print(opp.type, opp.title, opp.confidence)
    """

    def __init__(self, extra_scanners: Optional[List[BaseScanner]] = None) -> None:
        self._arxiv = ArxivScanner()
        self._pubmed = PubMedScanner()
        self._wiki = WikipediaScanner()
        self._extra = extra_scanners or []

    def scan(
        self,
        arxiv_categories: List[str] | None = None,
        arxiv_max: int = 30,
        pubmed_query: str = "machine learning",
        pubmed_max: int = 20,
        wikipedia_topics: List[str] | None = None,
    ) -> List[RawDocument]:
        docs: List[RawDocument] = []

        docs.extend(self._arxiv.scan(
            categories=arxiv_categories or ["cs.AI", "physics.gen-ph"],
            max_results=arxiv_max,
        ))
        docs.extend(self._pubmed.scan(query=pubmed_query, max_results=pubmed_max))
        docs.extend(self._wiki.scan(topics=wikipedia_topics))
        for scanner in self._extra:
            try:
                docs.extend(scanner.scan())
            except Exception:
                pass

        return docs

    def analyze(self, docs: List[RawDocument]) -> List[Opportunity]:
        opportunities: List[Opportunity] = []
        opportunities.extend(find_cross_domain_connections(docs))
        opportunities.extend(detect_blind_spots(docs))
        opportunities.extend(detect_emerging_signals(docs))
        opportunities.sort(key=lambda o: o.confidence, reverse=True)
        return opportunities

    def run(self, **scan_kwargs) -> List[Opportunity]:
        docs = self.scan(**scan_kwargs)
        return self.analyze(docs)

    def summary(self, opportunities: List[Opportunity]) -> Dict:
        by_type: Dict[str, int] = {}
        for o in opportunities:
            k = o.type.value
            by_type[k] = by_type.get(k, 0) + 1
        return {
            "total_opportunities": len(opportunities),
            "by_type": by_type,
            "top_entities": self._top_entities(opportunities),
        }

    def _top_entities(self, opportunities: List[Opportunity]) -> List[str]:
        freq: Dict[str, int] = {}
        for o in opportunities:
            for e in o.entities:
                freq[e] = freq.get(e, 0) + 1
        return sorted(freq, key=freq.get, reverse=True)[:10]  # type: ignore[arg-type]
