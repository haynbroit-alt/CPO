"""Shared CPO proof-creation logic used by the API and the Swarm executor."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .canon import canonicalize
from .crypto import (
    get_rotation_id,
    load_private_key,
    node_id,
    public_key_bytes,
    sha256,
    sign,
)
from .executor import execute as sandbox_execute
from .models import CPO, ExecutionResult
from .storage import append

# Module-level identity (loaded once per process, same key as main.py)
_PRIVATE_KEY = load_private_key()
_PUB_BYTES = public_key_bytes(_PRIVATE_KEY)
NODE_ID = node_id(_PUB_BYTES)
ROTATION_ID = get_rotation_id()


def canonical_payload(cpo: CPO) -> str:
    """Return the deterministic string that is hashed and signed for a CPO."""
    d = cpo.model_dump(exclude={"signature", "content_hash", "cpo_id", "signer"})
    if d.get("created_at") is not None:
        d["created_at"] = cpo.created_at.isoformat()
    return canonicalize(d)


def prove(cpo: CPO, result: ExecutionResult) -> CPO:
    """Attach result, sign, hash, append to ledger. Returns the mutated CPO."""
    cpo.cpo_id = str(uuid.uuid4())
    cpo.created_by = NODE_ID
    cpo.created_at = datetime.now(tz=timezone.utc)
    cpo.rotation_id = ROTATION_ID
    cpo.result = result

    payload = canonical_payload(cpo)
    cpo.content_hash = sha256(payload)
    cpo.signature = sign(_PRIVATE_KEY, payload).hex()
    cpo.signer = _PUB_BYTES.hex()

    append(cpo.model_dump())
    return cpo


def execute_and_prove(cpo: CPO) -> tuple[ExecutionResult, CPO]:
    """Execute in sandbox then produce a signed, ledger-appended CPO."""
    result = sandbox_execute(cpo)
    proved_cpo = prove(cpo, result)
    return result, proved_cpo
