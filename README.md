# Proof Protocol

A unified verifiable computation layer across all AI paradigm worlds.

Every claim produces a **Computational Proof Object (CPO)** — an immutable,
cryptographically-signed record that bundles the hypothesis, the code that
tests it, the sandboxed execution result, and the node identity that produced
it.

## Supported Worlds

| World | Key Libraries | Docker Image |
|---|---|---|
| `llm` | stdlib | `proof-protocol/sandbox:latest` |
| `symbolic` | SymPy, Z3 | `proof-protocol/symbolic:latest` |
| `neuro` | DSPy, LangChain | `proof-protocol/neuro:latest` |
| `bayesian` | NumPyro, PyMC | `proof-protocol/bayesian:latest` |
| `evolutionary` | DEAP, Mesa | `proof-protocol/evolutionary:latest` |
| `formal` | Z3, py-aiger | `proof-protocol/formal:latest` |
| `multimodal` | PyTorch CPU, Pillow | `proof-protocol/multimodal:latest` |

## Project Layout

```
proof-protocol/
├── app/
│   ├── main.py        # FastAPI node
│   ├── models.py      # CPO Pydantic schemas
│   ├── crypto.py      # Ed25519 signing + SHA-256
│   ├── canon.py       # RFC 8785-style canonical JSON
│   ├── executor.py    # Docker sandbox router
│   └── storage.py     # Append-only JSONL ledger
├── sandbox/
│   └── Dockerfile     # Base LLM sandbox image
├── docker/
│   ├── build_worlds.sh
│   └── worlds/        # One Dockerfile per AI world
├── tests/
├── config.py
├── requirements.txt
└── .env.example
```

## Quick Start

```bash
# 1. Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Build sandbox images (requires Docker)
bash docker/build_worlds.sh

# 3. Copy and edit environment
cp .env.example .env

# 4. Run the node
uvicorn app.main:app --reload
```

## API

### `POST /prove`

Submit a claim for execution.

```json
{
  "world": "symbolic",
  "claim": "x^2 - 1 factors as (x-1)(x+1)",
  "code": "from sympy import symbols, factor; x=symbols('x'); print(factor(x**2-1))"
}
```

Response:
```json
{
  "status": "accepted",
  "cpo_id": "...",
  "world": "symbolic",
  "content_hash": "sha256hex...",
  "exit_code": 0,
  "runtime_ms": 142.3,
  "signature": "ed25519hex..."
}
```

### `GET /cpo/{cpo_id}`

Retrieve a stored CPO by ID.

### `GET /verify/{content_hash}`

Re-execute the CPO and verify that the result and signature are consistent.

### `GET /ledger?world=symbolic&limit=50`

Browse the append-only ledger, optionally filtered by world.

## Security Properties

- **Isolation** — each sandbox runs with `network_disabled=True`, `read_only=True`, a memory cap, and `no-new-privileges`.
- **Integrity** — SHA-256 of the canonical (RFC 8785) serialisation is stored.
- **Non-repudiation** — Ed25519 signature over the canonical payload, keyed to the node identity.
- **Determinism** — constrained execution environment makes re-verification possible.

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```
