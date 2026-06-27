import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.brain import generate_code
from app.canon import canonicalize
from app.crypto import (
    get_rotation_id,
    load_private_key,
    node_id,
    public_key_bytes,
    sha256,
    sign,
    verify,
)
from app.executor import execute
from app.models import Attestation, CPO, CPOState, ExecutionResult, PeerNode
from app.peers import (
    add_attestation,
    all_peers,
    compute_state,
    get_attestations,
    register_peer,
)
from app.storage import all_cpos, append, find_by_hash, find_by_id
from config import DEFAULT_WORLD, SUPPORTED_WORLDS

# ---------------------------------------------------------------------------
# Node initialisation
# ---------------------------------------------------------------------------
_PRIVATE_KEY = load_private_key()
_PUB_BYTES = public_key_bytes(_PRIVATE_KEY)
NODE_ID = node_id(_PUB_BYTES)
ROTATION_ID = get_rotation_id()

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
        "status": "Proof Protocol Node online",
        "node_id": NODE_ID,
        "worlds": sorted(SUPPORTED_WORLDS),
        "endpoints": [
            "/prove", "/ask", "/verify/{cpo_hash}", "/cpo/{cpo_id}", "/ledger",
            "/health", "/node",
            "/peers/announce", "/peers",
            "/attest/{cpo_hash}", "/cpo/{cpo_id}/attestations",
        ],
    }


@app.get("/health")
def health() -> Dict:
    return {"status": "ok"}


@app.get("/node")
def node_info() -> Dict:
    ledger_size = len(all_cpos())
    return {
        "node_id": NODE_ID,
        "public_key": _PUB_BYTES.hex(),
        "worlds": sorted(SUPPORTED_WORLDS),
        "ledger_size": ledger_size,
        "peer_count": len(all_peers()),
        "rotation_id": ROTATION_ID,
        "version": "1.0.0",
    }


# ---------------------------------------------------------------------------
# Distributed network layer
# ---------------------------------------------------------------------------

@app.post("/peers/announce", status_code=201)
def announce_peer(peer: PeerNode) -> Dict:
    """Register a remote node as a known peer."""
    registered = register_peer(peer)
    return {
        "status": "registered",
        "node_id": registered.node_id,
        "announced_at": registered.announced_at.isoformat() if registered.announced_at else None,
    }


@app.get("/peers")
def list_peers() -> List[Dict]:
    """Return all known peer nodes."""
    return [p.model_dump() for p in all_peers()]


@app.post("/attest/{content_hash}", status_code=201)
def attest_cpo(content_hash: str) -> Dict:
    """Re-execute a CPO locally, sign the verdict, and record the attestation.

    Any node can call this on any peer.  The signed verdict is stored in the
    attestation registry and contributes to quorum computation.
    """
    record = find_by_hash(content_hash)
    if record is None:
        raise HTTPException(status_code=404, detail="CPO not found")

    original = CPO(**record)

    # Signature integrity check
    signer_bytes = bytes.fromhex(original.signer)
    payload = _cpo_canonical_payload(original)
    sig_bytes_orig = bytes.fromhex(original.signature)
    sig_ok = verify(signer_bytes, payload, sig_bytes_orig)

    # Re-execution
    fresh = execute(original)
    stdout_match = fresh.stdout.strip() == (original.result.stdout if original.result else "").strip()
    exit_match = fresh.exit_code == (original.result.exit_code if original.result else -1)
    verdict = sig_ok and stdout_match and exit_match

    # Sign the attestation payload: "<hash>:<verdict>"
    attest_payload = f"{content_hash}:{int(verdict)}"
    attest_sig = sign(_PRIVATE_KEY, attest_payload).hex()

    attestation = Attestation(
        node_id=NODE_ID,
        public_key=_PUB_BYTES.hex(),
        cpo_hash=content_hash,
        verdict=verdict,
        signature=attest_sig,
        timestamp=datetime.now(tz=timezone.utc),
    )
    add_attestation(attestation)

    state = compute_state(content_hash)
    return {
        "node_id": NODE_ID,
        "cpo_hash": content_hash,
        "verdict": verdict,
        "state": state.value,
        "signature": attest_sig,
        "timestamp": attestation.timestamp.isoformat(),
    }


@app.get("/cpo/{cpo_id}/attestations")
def get_cpo_attestations(cpo_id: str) -> Dict:
    """Return all attestations collected for a CPO and its current network state."""
    record = find_by_id(cpo_id)
    if record is None:
        raise HTTPException(status_code=404, detail="CPO not found")
    content_hash = record.get("content_hash", "")
    attestations = get_attestations(content_hash)
    state = compute_state(content_hash)
    return {
        "cpo_id": cpo_id,
        "content_hash": content_hash,
        "state": state.value,
        "attestation_count": len(attestations),
        "true_count": sum(1 for a in attestations if a.verdict),
        "false_count": sum(1 for a in attestations if not a.verdict),
        "attestations": [a.model_dump() for a in attestations],
    }


@app.post("/prove", status_code=201)
def prove(cpo: CPO) -> Dict:
    """Submit a claim for execution and produce a signed CPO."""
    cpo.cpo_id = str(uuid.uuid4())
    cpo.created_by = NODE_ID
    cpo.created_at = datetime.now(tz=timezone.utc)
    cpo.rotation_id = ROTATION_ID

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


# ---------------------------------------------------------------------------
# Conversational AI interface
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str
    world: str = DEFAULT_WORLD
    metadata: Dict[str, Any] = {}


@app.post("/ask", status_code=201)
def ask(req: AskRequest) -> Dict:
    """Convert a natural-language question into code, execute it, and return a verifiable proof."""
    if req.world not in SUPPORTED_WORLDS:
        raise HTTPException(status_code=422, detail=f"Unknown world '{req.world}'. Supported: {sorted(SUPPORTED_WORLDS)}")

    # 1. Generate code from the question
    try:
        code = generate_code(req.question, req.world)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Brain error: {exc}")

    if not code.strip():
        raise HTTPException(status_code=502, detail="Brain returned empty code")

    # 2. Build a CPO and execute in sandbox
    cpo = CPO(
        world=req.world,
        claim=req.question,
        code=code,
        metadata=req.metadata,
    )
    cpo.cpo_id = str(uuid.uuid4())
    cpo.created_by = NODE_ID
    cpo.created_at = datetime.now(tz=timezone.utc)
    cpo.rotation_id = ROTATION_ID

    try:
        result: ExecutionResult = execute(cpo)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sandbox error: {exc}")

    cpo.result = result

    # 3. Hash → sign → store
    payload = _cpo_canonical_payload(cpo)
    cpo.content_hash = sha256(payload)
    sig_bytes = sign(_PRIVATE_KEY, payload)
    cpo.signature = sig_bytes.hex()
    cpo.signer = _PUB_BYTES.hex()

    append(cpo.model_dump())

    return {
        "answer": result.stdout.strip(),
        "code": code,
        "cpo_id": cpo.cpo_id,
        "world": cpo.world,
        "proof_hash": cpo.content_hash,
        "signature": cpo.signature,
        "exit_code": result.exit_code,
        "runtime_ms": result.runtime_ms,
    }
