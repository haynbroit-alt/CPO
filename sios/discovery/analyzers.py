"""Discovery Engine analyzers — find hidden connections, blind spots, signals."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

from .models import Opportunity, OpportunityType
from .scanners.base import RawDocument


def find_cross_domain_connections(docs: List[RawDocument]) -> List[Opportunity]:
    """Detect shared concepts between documents from different sources/domains."""
    opportunities: List[Opportunity] = []
    seen: set = set()

    for i, d1 in enumerate(docs):
        for d2 in docs[i + 1:]:
            if d1.source == d2.source and d1.domain == d2.domain:
                continue
            common = set(d1.concepts) & set(d2.concepts)
            if len(common) < 2:
                continue
            key = (d1.title[:40], d2.title[:40])
            if key in seen:
                continue
            seen.add(key)

            confidence = min(0.5 + 0.05 * len(common), 0.90)
            opportunities.append(Opportunity(
                type=OpportunityType.CROSS_DOMAIN_CONNECTION,
                title=f"Cross-domain bridge: {d1.source} ↔ {d2.source}",
                description=(
                    f'"{d1.title[:70]}" ({d1.source}/{d1.domain}) and '
                    f'"{d2.title[:70]}" ({d2.source}/{d2.domain}) '
                    f"share {len(common)} concepts: {', '.join(sorted(common)[:5])}. "
                    f"This connection has not been explicitly drawn in either source."
                ),
                confidence=confidence,
                evidence=[
                    {"source": d1.source, "domain": d1.domain, "title": d1.title,
                     "url": d1.url},
                    {"source": d2.source, "domain": d2.domain, "title": d2.title,
                     "url": d2.url},
                    {"common_concepts": sorted(common)},
                ],
                sources=[d1.url, d2.url],
                entities=sorted(common),
                recommended_actions=[
                    "Explore whether the shared mathematical/conceptual framework can transfer",
                    "Search for existing literature at this intersection",
                    "Consider a cross-disciplinary literature review or hypothesis",
                ],
                discovery_engine="cross_domain_analyzer",
                discovery_domain="science",
            ))

    return sorted(opportunities, key=lambda o: o.confidence, reverse=True)


def detect_blind_spots(docs: List[RawDocument]) -> List[Opportunity]:
    """Flag concepts that appear rarely — potential under-researched areas."""
    if not docs:
        return []

    freq: Dict[str, int] = defaultdict(int)
    concept_docs: Dict[str, List[str]] = defaultdict(list)

    for doc in docs:
        for c in doc.concepts:
            freq[c] += 1
            concept_docs[c].append(doc.title[:60])

    if not freq:
        return []

    total = len(docs)
    threshold = max(1, total * 0.04)  # < 4% of docs

    rare = [(c, f) for c, f in freq.items() if f <= threshold and len(c) > 4]
    rare.sort(key=lambda x: x[1])

    opportunities: List[Opportunity] = []
    for concept, f in rare[:10]:
        rarity = 1.0 - (f / max(freq.values()))
        opportunities.append(Opportunity(
            type=OpportunityType.BLIND_SPOT,
            title=f"Under-researched concept: '{concept}'",
            description=(
                f"The concept '{concept}' appears in only {f}/{total} scanned documents "
                f"(rarity score {rarity:.2f}). This may represent a blind spot in "
                f"the literature — a domain where research is scarce relative to its "
                f"potential relevance."
            ),
            confidence=min(0.4 + rarity * 0.4, 0.80),
            evidence=[{"concept": concept, "frequency": f,
                        "rarity_score": round(rarity, 3),
                        "example_documents": concept_docs[concept][:3]}],
            entities=[concept],
            recommended_actions=[
                f"Conduct a systematic literature search for '{concept}'",
                "Check whether the concept appears under different terminology",
                "Consider this as a potential research opportunity",
            ],
            discovery_engine="blind_spot_analyzer",
            discovery_domain="science",
        ))

    return opportunities


def detect_emerging_signals(docs: List[RawDocument]) -> List[Opportunity]:
    """Concepts that appear in multiple recent documents — fast-rising signals."""
    if not docs:
        return []

    freq: Dict[str, int] = defaultdict(int)
    domain_presence: Dict[str, set] = defaultdict(set)

    for doc in docs:
        for c in doc.concepts:
            freq[c] += 1
            domain_presence[c].add(doc.domain or doc.source)

    total = len(docs)
    # Emerging: moderately frequent AND spans multiple domains
    opportunities: List[Opportunity] = []
    for concept, f in freq.items():
        domains = domain_presence[concept]
        if f < 3 or len(domains) < 2 or len(concept) <= 4:
            continue
        cross_domain_score = len(domains) / 5.0
        frequency_score = min(f / (total * 0.3), 1.0)
        confidence = min(0.5 * cross_domain_score + 0.5 * frequency_score, 0.85)
        if confidence < 0.35:
            continue

        opportunities.append(Opportunity(
            type=OpportunityType.EMERGING_SIGNAL,
            title=f"Emerging signal: '{concept}' across {len(domains)} domains",
            description=(
                f"'{concept}' appears in {f} documents spanning "
                f"{len(domains)} different domains ({', '.join(sorted(domains))}). "
                f"Cross-domain convergence on a concept often precedes a breakthrough."
            ),
            confidence=confidence,
            evidence=[{"concept": concept, "frequency": f,
                        "domains": sorted(domains)}],
            entities=[concept],
            recommended_actions=[
                f"Monitor publication velocity for '{concept}' over the next 30 days",
                "Identify leading authors/labs at this intersection",
                "Check patent filings mentioning this concept",
            ],
            discovery_engine="emerging_signal_analyzer",
            discovery_domain="science",
        ))

    return sorted(opportunities, key=lambda o: o.confidence, reverse=True)[:10]
