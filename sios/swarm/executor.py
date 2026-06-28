"""Spore executor — runs a Spore in the CPO sandbox and attaches a proof."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Tuple

from app.models import CPO
from app.prove import execute_and_prove
from sios.swarm.models import FitnessSignal, Spore

logger = logging.getLogger(__name__)


def execute_spore(
    spore: Spore,
    node_id: str,
    timeout_ms: float = 5000.0,
) -> Tuple[bool, FitnessSignal]:
    """
    Execute a Spore inside the BEE sandbox (same Docker/subprocess executor
    used by the Proof Protocol).

    Returns (success, FitnessSignal). The CPO ID is captured in both the
    signal and appended to spore.cpo_ids for a full proof trail.
    """
    cpo = CPO(
        world="llm",
        claim=f"[swarm] spore:{spore.id} gen:{spore.generation}",
        code=spore.code,
    )

    t0 = time.monotonic()
    try:
        result, proved_cpo = execute_and_prove(cpo)
    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
        logger.warning("Spore %s execution failed: %s", spore.id[:8], exc)
        return False, FitnessSignal(
            node_id=node_id,
            spore_id=spore.id,
            score=0.0,
            execution_time_ms=elapsed,
            output_hash=hashlib.sha256(b"error").hexdigest(),
            notes=str(exc)[:200],
        )

    elapsed = (time.monotonic() - t0) * 1000
    stdout = (result.stdout or "").strip()
    output_hash = hashlib.sha256(stdout.encode()).hexdigest()

    # Fitness heuristic: success → base 0.5; non-empty output → +0.25; fast runtime → +0.25
    if result.exit_code != 0:
        score = 0.0
    else:
        score = 0.5
        if stdout:
            score += 0.25
        # Runtime bonus: under 100ms → +0.25, degrades linearly to 0 at timeout
        runtime_bonus = max(0.0, 0.25 * (1 - elapsed / timeout_ms))
        score = min(score + runtime_bonus, 1.0)

    signal = FitnessSignal(
        node_id=node_id,
        spore_id=spore.id,
        score=round(score, 3),
        execution_time_ms=round(elapsed, 1),
        output_hash=output_hash,
        cpo_id=proved_cpo.cpo_id,          # proof trail attached
    )

    # Attach CPO ID to the Spore's proof history
    if proved_cpo.cpo_id:
        spore.cpo_ids.append(proved_cpo.cpo_id)

    return result.exit_code == 0, signal
