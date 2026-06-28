"""Evolutionary engine — selection, mutation, reproduction of Spores.

Three mutation strategies:
  1. Cosmetic  — adds a comment; code semantics unchanged (tests lineage tracking)
  2. Parametric — changes numeric literals within ±20 % (safe, bounded)
  3. LLM-guided — asks the brain module for a functional variation (most powerful)
"""

from __future__ import annotations

import hashlib
import random
import re
import uuid
from typing import List, Optional, Tuple

from .models import Spore, SporeStatus


# ---------------------------------------------------------------------------
# Fitness thresholds
# ---------------------------------------------------------------------------
ALIVE_THRESHOLD = 0.4        # fitness must exceed this to be ALIVE
EXTINCTION_THRESHOLD = 0.1   # below this → EXTINCT
REPRODUCE_THRESHOLD = 0.6    # must exceed this to produce children
MAX_POPULATION = 500         # hard cap (prevents unbounded growth)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def tournament_select(
    population: List[Spore],
    k: int = 3,
    n: int = 1,
) -> List[Spore]:
    """Tournament selection — pick n winners from k-way tournaments."""
    alive = [s for s in population if s.status == SporeStatus.ALIVE]
    if not alive:
        return []
    winners: List[Spore] = []
    for _ in range(n):
        contestants = random.sample(alive, min(k, len(alive)))
        winners.append(max(contestants, key=lambda s: s.fitness))
    return winners


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------

def _mutate_cosmetic(spore: Spore) -> Spore:
    tag = uuid.uuid4().hex[:6]
    new_code = spore.code + f"\n# evolved_{tag}"
    return Spore(
        code=new_code,
        description=spore.description,
        parent_id=spore.id,
        generation=spore.generation + 1,
        mutation_notes=f"cosmetic: tag {tag}",
        created_by=spore.created_by,
    )


def _mutate_parametric(spore: Spore) -> Spore:
    """Perturb numeric literals by ±20 % (integers and floats)."""
    def perturb(m: re.Match) -> str:
        val = float(m.group(0))
        factor = random.uniform(0.80, 1.20)
        new_val = val * factor
        return str(int(new_val)) if m.group(0).isdigit() else f"{new_val:.4f}"

    new_code = re.sub(r"\b\d+\.?\d*\b", perturb, spore.code)
    return Spore(
        code=new_code,
        description=spore.description,
        parent_id=spore.id,
        generation=spore.generation + 1,
        mutation_notes="parametric: numeric literals perturbed ±20%",
        created_by=spore.created_by,
    )


def _mutate_llm(spore: Spore) -> Optional[Spore]:
    """Ask the brain module for a functional variation of the code."""
    try:
        from app.brain import generate_code  # lazy import — requires ANTHROPIC_API_KEY

        prompt = (
            f"Rewrite this Python program with a small functional improvement "
            f"or optimisation. Keep it short (under 30 lines). "
            f"Return ONLY the Python code, no explanation.\n\n"
            f"Original:\n{spore.code}"
        )
        new_code = generate_code(prompt, world="llm")
        if not new_code.strip():
            return None
        return Spore(
            code=new_code,
            description=f"LLM variation of: {spore.description}",
            parent_id=spore.id,
            generation=spore.generation + 1,
            mutation_notes="llm-guided: functional variation",
            created_by=spore.created_by,
        )
    except Exception:
        return None


def mutate(
    spore: Spore,
    strategy: str = "auto",
    llm_available: bool = False,
) -> Optional[Spore]:
    """
    Produce one child Spore via mutation.

    strategy:
      "cosmetic"   — always safe, tests lineage only
      "parametric" — perturbs numeric constants
      "llm"        — LLM-guided functional variation (requires ANTHROPIC_API_KEY)
      "auto"       — tries llm if available, falls back to parametric
    """
    if strategy == "cosmetic":
        return _mutate_cosmetic(spore)
    if strategy == "parametric":
        return _mutate_parametric(spore)
    if strategy == "llm":
        result = _mutate_llm(spore) if llm_available else None
        return result or _mutate_cosmetic(spore)
    # auto
    if llm_available:
        result = _mutate_llm(spore)
        if result:
            return result
    return _mutate_parametric(spore)


# ---------------------------------------------------------------------------
# Evolution cycle
# ---------------------------------------------------------------------------

class EvolutionEngine:
    """One full evolutionary cycle over the local spore population.

    Lifecycle:
      1. Update fitness for all spores (aggregate signals)
      2. Apply ALIVE / DORMANT / EXTINCT labels
      3. Select reproducers (tournament, fitness > REPRODUCE_THRESHOLD)
      4. Mutate and produce children
      5. Enforce population cap (evict least fit)
    """

    def __init__(
        self,
        mutation_strategy: str = "auto",
        llm_available: bool = False,
        max_children_per_cycle: int = 5,
    ) -> None:
        self.mutation_strategy = mutation_strategy
        self.llm_available = llm_available
        self.max_children = max_children_per_cycle

    def step(self, population: List[Spore]) -> Tuple[List[Spore], List[Spore]]:
        """Execute one evolution step.

        Returns (updated_population, new_children).
        """
        # 1. Recompute fitness
        for spore in population:
            spore.update_fitness()

        # 2. Update statuses
        for spore in population:
            if spore.fitness >= ALIVE_THRESHOLD:
                spore.status = SporeStatus.ALIVE
            elif spore.fitness >= EXTINCTION_THRESHOLD:
                spore.status = SporeStatus.DORMANT
            else:
                spore.status = SporeStatus.EXTINCT

        # 3. Select reproducers
        alive = [s for s in population if s.fitness >= REPRODUCE_THRESHOLD]
        reproducers = tournament_select(
            population, k=3, n=min(self.max_children, len(alive))
        )

        # 4. Mutate → children
        children: List[Spore] = []
        for parent in reproducers:
            child = mutate(parent, self.mutation_strategy, self.llm_available)
            if child:
                parent.status = SporeStatus.MUTATED
                children.append(child)

        # 5. Merge and cap
        all_spores = population + children
        if len(all_spores) > MAX_POPULATION:
            all_spores.sort(key=lambda s: s.fitness, reverse=True)
            all_spores = all_spores[:MAX_POPULATION]

        return all_spores, children
