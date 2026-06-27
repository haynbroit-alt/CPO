import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.canon import canonicalize
from app.crypto import (
    load_private_key,
    node_id,
    public_key_bytes,
    sha256,
    sign,
    verify,
)
from app.executor import execute
from app.models import CPO, ExecutionResult
from app.storage import all_cpos, append, find_by_hash, find_by_id
from config import SUPPORTED_WORLDS

# ---------------------------------------------------------------------------
# Node initialisation
# ---------------------------------------------------------------------------
_PRIVATE_KEY = load_private_key()
_PUB_BYTES = public_key_bytes(_PRIVATE_KEY)
NODE_ID = node_id(_PUB_BYTES)

app = FastAPI(
    title="Proof Protocol Node",
    version="1.0.0",
    description="Unified verifiable computation layer across all AI paradigm worlds.",
)


@app.on_event("startup")
async def _startup() -> None:
    print(f"[Proof Protocol] Node ID : {NODE_ID}")
    print(f"[Proof Protocol] Worlds  : {sorted(SUPPORTED_WORLDS)}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cpo_canonical_payload(cpo: CPO) -> str:
    """Return the canonical string that is hashed and signed.

    Excludes mutable fields set *after* execution (signature, content_hash,
    cpo_id) so the payload covers exactly the meaningful content.
    """
    d: Dict[str, Any] = cpo.model_dump(
        exclude={"signature", "content_hash", "cpo_id", "signer"}
    )
    # Normalise datetime to ISO string for determinism
    if d.get("created_at") is not None:
        d["created_at"] = cpo.created_at.isoformat()
    return canonicalize(d)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def index() -> Dict:
    return {
        "node_id": NODE_ID,
        "worlds": sorted(SUPPORTED_WORLDS),
        "endpoints": ["/prove", "/verify/{cpo_hash}", "/cpo/{cpo_id}", "/ledger"],
    }


@app.post("/prove", status_code=201)
def prove(cpo: CPO) -> Dict:
    """Submit a claim for execution and produce a signed CPO."""
    cpo.cpo_id = str(uuid.uuid4())
    cpo.created_by = NODE_ID
    cpo.created_at = datetime.now(tz=timezone.utc)

    # Execute inside sandbox
    try:
        result: ExecutionResult = execute(cpo)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sandbox error: {exc}")

    cpo.result = result

    # Hash → sign
    payload = _cpo_canonical_payload(cpo)
    cpo.content_hash = sha256(payload)
    sig_bytes = sign(_PRIVATE_KEY, payload)
    cpo.signature = sig_bytes.hex()
    cpo.signer = _PUB_BYTES.hex()

    append(cpo.model_dump())

    return {
        "status": "accepted",
        "cpo_id": cpo.cpo_id,
        "world": cpo.world,
        "content_hash": cpo.content_hash,
        "exit_code": result.exit_code,
        "runtime_ms": result.runtime_ms,
        "signature": cpo.signature,
    }


@app.get("/cpo/{cpo_id}")
def get_cpo(cpo_id: str) -> Dict:
    record = find_by_id(cpo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="CPO not found")
    return record


@app.get("/verify/{content_hash}")
def verify_cpo(content_hash: str) -> Dict:
    """Re-execute a stored CPO and confirm the result matches the original."""
    record = find_by_hash(content_hash)
    if record is None:
        raise HTTPException(status_code=404, detail="CPO not found")

    original = CPO(**record)

    # Signature check
    signer_bytes = bytes.fromhex(original.signer)
    payload = _cpo_canonical_payload(original)
    sig_bytes = bytes.fromhex(original.signature)
    sig_valid = verify(signer_bytes, payload, sig_bytes)

    # Re-execution
    fresh = execute(original)
    stdout_match = fresh.stdout.strip() == (original.result.stdout if original.result else "").strip()
    exit_match = fresh.exit_code == (original.result.exit_code if original.result else -1)

    return {
        "content_hash": content_hash,
        "signature_valid": sig_valid,
        "stdout_match": stdout_match,
        "exit_code_match": exit_match,
        "verified": sig_valid and stdout_match and exit_match,
        "original_exit_code": original.result.exit_code if original.result else None,
        "fresh_exit_code": fresh.exit_code,
        "original_stdout": original.result.stdout if original.result else "",
        "fresh_stdout": fresh.stdout,
    }


@app.get("/ledger")
def ledger(world: str | None = None, limit: int = 50) -> List[Dict]:
    records = all_cpos()
    if world:
        records = [r for r in records if r.get("world") == world]
    return records[-limit:]
