"""In-memory peer registry and attestation store.

Both stores are process-local and ephemeral — suitable for single-node demos
and multi-node deployments where each node maintains its own view of the
network. Persistence can be added by serialising to the JSONL ledger.
"""

from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List

from app.models import Attestation, CPOState, PeerNode
from config import QUORUM_THRESHOLD

_peer_lock = Lock()
_attest_lock = Lock()

# node_id → PeerNode
_peers: Dict[str, PeerNode] = {}

# cpo_hash → list[Attestation]
_attestations: Dict[str, List[Attestation]] = {}


# ---------------------------------------------------------------------------
# Peers
# ---------------------------------------------------------------------------

def register_peer(peer: PeerNode) -> PeerNode:
    if peer.announced_at is None:
        peer.announced_at = datetime.now(tz=timezone.utc)
    with _peer_lock:
        _peers[peer.node_id] = peer
    return peer


def all_peers() -> List[PeerNode]:
    with _peer_lock:
        return list(_peers.values())


def peer_count() -> int:
    with _peer_lock:
        return len(_peers)


# ---------------------------------------------------------------------------
# Attestations
# ---------------------------------------------------------------------------

def add_attestation(attestation: Attestation) -> None:
    with _attest_lock:
        bucket = _attestations.setdefault(attestation.cpo_hash, [])
        # One attestation per node_id; replace if re-attested
        bucket[:] = [a for a in bucket if a.node_id != attestation.node_id]
        bucket.append(attestation)


def get_attestations(cpo_hash: str) -> List[Attestation]:
    with _attest_lock:
        return list(_attestations.get(cpo_hash, []))


# ---------------------------------------------------------------------------
# Quorum + state
# ---------------------------------------------------------------------------

def compute_state(cpo_hash: str) -> CPOState:
    """Derive the CPO's network state from collected attestations.

    Decision rules (in precedence order, matching Definition 11 in the paper):
    1. Quorum of ⊤ → VERIFIED
    2. Quorum of ⊥ → INVALID
    3. Any attestations but no quorum → CONTESTED
    4. No attestations → PROPOSED
    """
    attestations = get_attestations(cpo_hash)
    n = len(attestations)
    if n == 0:
        return CPOState.PROPOSED

    true_count = sum(1 for a in attestations if a.verdict)
    false_count = n - true_count

    # Quorum: need strictly more than QUORUM_THRESHOLD fraction
    quorum_k = max(1, int(n * QUORUM_THRESHOLD) + 1) if n > 1 else 1
    if n == 1:
        quorum_k = 1

    if true_count >= quorum_k:
        return CPOState.VERIFIED
    if false_count >= quorum_k:
        return CPOState.INVALID
    return CPOState.CONTESTED
