"""SwarmNode — local registry of spores with evolution + P2P gossip."""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .evolution import EvolutionEngine, ALIVE_THRESHOLD
from .executor import execute_spore
from .models import FitnessSignal, Spore, SporeStatus, SwarmStats


class SwarmNode:
    """
    A voluntary participant in the SIOS Swarm.

    - Maintains a local population of Spores.
    - Executes Spores in the CPO sandbox (BEE).
    - Scores fitness and propagates top Spores to peers.
    - Runs one evolution cycle per `evolve()` call.

    Consent contract:
      A node joins by calling SwarmNode.__init__().
      Spores are only accepted via ingest(), never pushed without API call.
      The operator can call purge() at any time to remove all spores.
    """

    def __init__(self, node_id: str, llm_available: bool = False) -> None:
        self.node_id = node_id
        self._population: Dict[str, Spore] = {}
        self._evolution = EvolutionEngine(llm_available=llm_available)

    # ── Ingestion ─────────────────────────────────────────────────────────────

    def ingest(self, spore: Spore) -> bool:
        """Accept a Spore into the local population (returns False if duplicate)."""
        if spore.id in self._population:
            return False
        spore.created_by = spore.created_by or self.node_id
        self._population[spore.id] = spore
        return True

    def ingest_many(self, spores: List[Spore]) -> int:
        return sum(1 for s in spores if self.ingest(s))

    # ── Execution ─────────────────────────────────────────────────────────────

    def execute(self, spore_id: str) -> Optional[FitnessSignal]:
        """Execute one Spore in the BEE sandbox and record the fitness signal."""
        spore = self._population.get(spore_id)
        if spore is None:
            return None

        success, signal = execute_spore(spore, self.node_id)
        spore.fitness_signals.append(signal)
        spore.update_fitness()
        spore.execution_count += 1
        spore.last_executed_at = datetime.now(tz=timezone.utc)

        if success and spore.status == SporeStatus.PROPOSED:
            spore.status = SporeStatus.ALIVE if spore.fitness >= ALIVE_THRESHOLD else SporeStatus.DORMANT

        return signal

    def execute_all(self) -> List[FitnessSignal]:
        """Execute every PROPOSED / ALIVE spore once."""
        signals = []
        for spore in list(self._population.values()):
            if spore.status in (SporeStatus.PROPOSED, SporeStatus.ALIVE):
                sig = self.execute(spore.id)
                if sig:
                    signals.append(sig)
        return signals

    # ── Evolution ─────────────────────────────────────────────────────────────

    def evolve(self) -> List[Spore]:
        """Run one evolution cycle; return newly created children."""
        population = list(self._population.values())
        updated, children = self._evolution.step(population)
        self._population = {s.id: s for s in updated}
        for child in children:
            self._population[child.id] = child
        return children

    # ── Gossip / P2P ──────────────────────────────────────────────────────────

    def top_spores(self, n: int = 10) -> List[Spore]:
        """Return the n highest-fitness Spores for sharing with peers."""
        alive = [s for s in self._population.values() if s.status == SporeStatus.ALIVE]
        return sorted(alive, key=lambda s: s.fitness, reverse=True)[:n]

    def receive_from_peer(self, spores: List[Spore]) -> int:
        """Accept Spores propagated from a peer node. Returns count ingested."""
        return self.ingest_many(spores)

    # ── Stats ──────────────────────────────────────────────────────────────────

    def stats(self) -> SwarmStats:
        pop = list(self._population.values())
        alive = [s for s in pop if s.status == SporeStatus.ALIVE]
        fitness_vals = [s.fitness for s in pop if s.fitness > 0]
        return SwarmStats(
            total_spores=len(pop),
            alive_count=len(alive),
            dormant_count=sum(1 for s in pop if s.status == SporeStatus.DORMANT),
            extinct_count=sum(1 for s in pop if s.status == SporeStatus.EXTINCT),
            total_executions=sum(s.execution_count for s in pop),
            mean_fitness=round(statistics.mean(fitness_vals), 3) if fitness_vals else 0.0,
            max_fitness=round(max(fitness_vals), 3) if fitness_vals else 0.0,
            max_generation=max((s.generation for s in pop), default=0),
            top_spore_ids=[s.id for s in self.top_spores(5)],
        )

    def purge(self) -> int:
        """Remove all spores (consent revocation). Returns count removed."""
        n = len(self._population)
        self._population.clear()
        return n

    def get(self, spore_id: str) -> Optional[Spore]:
        return self._population.get(spore_id)

    def all(self) -> List[Spore]:
        return list(self._population.values())
