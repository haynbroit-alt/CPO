# Proof Protocol

**The open protocol for verifiable AI computation.**

> Every AI output is a claim. Proof Protocol turns claims into cryptographic proofs.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com)

```
✓ Replay-based verification          ✓ Cryptographic Computational Proof Objects (CPO)
✓ Deterministic sandbox execution    ✓ Multi-world AI runtime (7 paradigms)
✓ Distributed multi-node attestation ✓ LangChain + DSPy integrations
```

---

## How it works

```
  LLM / Agent / Script
          │
          ▼
  Proof Protocol Node          ←── POST /prove  {"claim": ..., "code": ..., "world": ...}
          │
          ▼
  Bounded Execution            ←── sandboxed Python, network off, memory capped
  Environment (BEE)
          │
          ▼
  Computational Proof          ←── (world, claim, code, stdout, exit_code, timestamp, node_id)
  Object  (CPO)
          │
          ▼
  Ed25519 Signature            ←── SHA-256(canonical_json(CPO))  →  sign(private_key)
          │
          ▼
  Immutable JSONL Ledger       ←── append-only, content-addressed
          │
          ▼
  Replay Verification          ←── GET /verify/{hash}  →  re-execute + compare stdout
```

Any node, at any time, can re-execute a CPO and confirm the result matches the original. No trusted third party required.

---

## Why

AI systems produce outputs that are unverifiable by design. A language model can claim any answer; a code-generation agent can produce any output. There is no standard mechanism to prove that a given output was produced by a specific computation, running in a specific environment, at a specific time.

Proof Protocol solves this with three primitives:

1. **Bounded Execution Environment (BEE)** — a sandboxed Python runtime with deterministic observable behavior (stdout + exit code).
2. **Computational Proof Object (CPO)** — a signed, content-addressed record that bundles hypothesis, code, and execution result.
3. **Replay Verification** — re-execute the CPO and compare; no special hardware or ZK circuits required.

---

## Quick start

```bash
# Clone and install
git clone https://github.com/haynbroit-alt/cpo.git && cd cpo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure (set ANTHROPIC_API_KEY for /ask)
cp .env.example .env

# Run a node
uvicorn app.main:app --reload
```

```bash
# Prove a claim
curl -X POST http://localhost:8000/prove \
  -H "Content-Type: application/json" \
  -d '{"world":"symbolic","claim":"x²-1 factors as (x-1)(x+1)",
       "code":"from sympy import symbols,factor; x=symbols(\"x\"); print(factor(x**2-1))"}'

# → {"cpo_id":"...","content_hash":"sha256...","signature":"ed25519...","exit_code":0}

# Verify (re-execute and compare)
curl http://localhost:8000/verify/<content_hash>

# → {"verified":true,"signature_valid":true,"stdout_match":true}
```

---

## API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/prove` | Execute code in the sandbox, return a signed CPO |
| `POST` | `/ask` | NL question → LLM-generated code → signed CPO |
| `GET` | `/verify/{hash}` | Re-execute a CPO and verify result + signature |
| `GET` | `/cpo/{id}` | Retrieve a stored CPO by ID |
| `GET` | `/ledger` | Browse the append-only ledger (`?world=symbolic&limit=50`) |
| `GET` | `/node` | Node identity, public key, worlds, ledger size |
| `GET` | `/health` | Health check |
| `POST` | `/peers/announce` | Register a peer node |
| `POST` | `/attest/{hash}` | Peer attestation: re-execute + sign verdict |
| `GET` | `/cpo/{id}/attestations` | Quorum state across all attesting nodes |

---

## Execution worlds

| World | Paradigm | Key Libraries |
|---|---|---|
| `llm` | General-purpose | stdlib |
| `symbolic` | Computer algebra | SymPy, Z3 |
| `neuro` | Neural computation | PyTorch CPU, DSPy |
| `bayesian` | Probabilistic inference | NumPyro, PyMC |
| `evolutionary` | Genetic algorithms | DEAP, Mesa |
| `formal` | Formal verification | Z3, py-aiger |
| `multimodal` | Vision + language | PyTorch, Pillow |

---

## Integrations

### LangChain

```bash
pip install langchain-cpo
```

```python
from langchain_openai import ChatOpenAI
from langchain_cpo import CPOCallbackHandler, CPOClient

llm = ChatOpenAI(callbacks=[CPOCallbackHandler(CPOClient("https://your-node.onrender.com"))])
result = llm.invoke("What is the square root of 144?")
print(result.response_metadata["cpo_hash"])  # every output is attested
```

→ [`integrations/langchain_cpo/`](integrations/langchain_cpo/)

### DSPy

```bash
pip install dspy-cpo
```

```python
from dspy_cpo import CPOModule, CPOClient

rag = CPOModule(MyRAG(), CPOClient("https://your-node.onrender.com"))
pred = rag(question="Who invented the telephone?")
print(pred.cpo_verified)  # True
```

→ [`integrations/dspy_cpo/`](integrations/dspy_cpo/)

---

## Security properties

| Property | Mechanism |
|---|---|
| Isolation | `network_disabled=True`, `read_only=True`, memory cap, `no-new-privileges` |
| Integrity | SHA-256 of RFC 8785 canonical JSON |
| Non-repudiation | Ed25519 signature keyed to node identity |
| Determinism | Constrained BEE makes stdout reproducible |
| Key rotation | `NODE_KEY_ROTATION_ID` epochs; old CPOs remain verifiable (pk embedded inline) |

---

## Distributed attestation

Multiple nodes can independently re-execute a CPO and sign their verdict. The quorum state machine:

```
PROPOSED  →  ATTESTED  →  VERIFIED   (≥ threshold of true attestations)
                       →  INVALID    (≥ threshold of false attestations)
                       →  CONTESTED  (split attestations, no quorum)
```

---

## Project layout

```
proof-protocol/
├── app/
│   ├── main.py        # FastAPI node (all routes)
│   ├── models.py      # CPO, Attestation, PeerNode schemas
│   ├── crypto.py      # Ed25519, SHA-256, key rotation
│   ├── canon.py       # RFC 8785 canonical JSON
│   ├── executor.py    # Docker / subprocess sandbox router
│   ├── peers.py       # Peer registry + quorum computation
│   └── storage.py     # Append-only JSONL ledger
├── integrations/
│   ├── langchain_cpo/ # pip install langchain-cpo
│   └── dspy_cpo/      # pip install dspy-cpo
├── benchmarks/        # Latency + determinism benchmark suite
├── paper/             # Research paper (LaTeX)
├── scripts/           # Key generation helpers
├── tests/             # 29 passing tests
└── config.py
```

---

## Running tests

```bash
pip install pytest
pytest tests/ -v  # 29 tests, 0 warnings
```

---

## Roadmap

- [ ] PyPI publish (`langchain-cpo`, `dspy-cpo`)
- [ ] LlamaIndex adapter
- [ ] OpenTelemetry span export (CPO as trace attribute)
- [ ] Public ledger explorer (read-only web UI)
- [ ] P2P peer discovery (gossip protocol)
- [ ] Benchmark results published to `gh-pages`
- [ ] Docker images published to GHCR

---

## Research

A formal treatment of the Proof Protocol — including the CPO data model, the Bounded Execution Environment, decidability of verification (Theorem 1), and empirical latency benchmarks across all seven worlds — is available in [`paper/proof_protocol.tex`](paper/proof_protocol.tex).

---

## Deployment

A public node is deployed on Render. Set `NODE_PRIVATE_KEY_B64` (base64-encoded PEM) as an environment variable — see [`scripts/generate_node_key.py`](scripts/generate_node_key.py).

---

## License

MIT
