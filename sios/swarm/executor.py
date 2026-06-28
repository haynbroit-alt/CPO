"""Spore executor — runs a Spore in the CPO sandbox and attaches a proof."""

from __future__ import annotations

import hashlib
import time
from typing import Optional, Tuple

from app.models import CPO
from app.executor import execute as cpo_execute
from sios.swarm.models import FitnessSignal, Spore


def execute_spore(
    spore: Spore,
    node_id: str,
    timeout_ms: float = 5000.0,
) -> Tuple[bool, FitnessSignal]:
    """
    Execute a Spore inside the BEE sandbox (same Docker/subprocess executor
    used by the Proof Protocol).

    Returns (success, FitnessSignal). On success, the CPO ID is recorded
    in the signal for proof retrieval.
    """
    cpo = CPO(
        world="llm",
        claim=f"[swarm] spore:{spore.id} gen:{spore.generation}",
        code=spore.code,
    )

    t0 = time.monotonic()
    try:
        result = cpo_execute(cpo)
    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
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

    # Fitness heuristic: success → base 0.5; shorter runtime → bonus; non-empty output → bonus
    if result.exit_code != 0:
        score = 0.0
    else:
        score = 0.5
        if stdout:
            score += 0.25
        # Runtime bonus: under 100ms → +0.25, degrades linearly to 0 at 5000ms
        runtime_bonus = max(0.0, 0.25 * (1 - elapsed / timeout_ms))
        score = min(score + runtime_bonus, 1.0)

    signal = FitnessSignal(
        node_id=node_id,
        spore_id=spore.id,
        score=round(score, 3),
        execution_time_ms=round(elapsed, 1),
        output_hash=output_hash,
    )
    return result.exit_code == 0, signal
