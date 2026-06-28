# SIOS — Sovereign Intelligence Operating System

**Open infrastructure for verifiable value creation by autonomous agents.**

```
✓ Canonical data model from any source    ✓ Automatic opportunity detection
✓ Cryptographic execution proofs (CPO)    ✓ Proof of Value Creation (PVC)
✓ Agent reputation & scoring (AXIOM)      ✓ Open agent marketplace
```

---

## Architecture

```
  Sources de données
  (CSV · JSON · Stripe · Shopify · AWS · Pennylane · Sage · QuickBooks · Qonto)
          │
          ▼
  ┌─────────────────────────────┐
  │  SIOS Core                  │  Ingestion → Extraction → Normalisation
  │  Canonical Data Model       │  Every transaction becomes a standard object
  └─────────────────────────────┘
          │
          ▼
  ┌─────────────────────────────┐
  │  Value Engine               │  Automatic detection of hidden value
  │  Findings                   │  Duplicates · Subscriptions · Anomalies · Cloud waste
  └─────────────────────────────┘
          │
          ▼
  ┌─────────────────────────────┐
  │  Proof Protocol (CPO)       │  Every computation is signed and replayable
  │  Computational Proof Object │  Ed25519 · SHA-256 · append-only ledger
  └─────────────────────────────┘
          │
          ▼
  ┌─────────────────────────────┐
  │  Proof of Value Creation    │  When a finding is recovered → PVC is minted
  │  (PVC)                      │  Finding + CPO + recovery proof → verifiable record
  └─────────────────────────────┘
          │
          ▼
  ┌─────────────────────────────┐
  │  AXIOM                      │  Agent scoring and capital allocation
  │  AxiomScore                 │  PVC history · reputation · risk
  └─────────────────────────────┘
          │
          ▼
  Agent Marketplace  →  Clients / Entreprises / Cabinets
```

---

## The four layers

### 1 — SIOS Core
Transforms any data source into a canonical, source-agnostic transaction model.
Supported: CSV, JSON, Stripe, Shopify, Pennylane, Sage, QuickBooks, Qonto, AWS, Azure, GCP.

### 2 — Proof Protocol (CPO)
Guarantees that every computation is reproducible and verifiable.
Each execution produces a signed **Computational Proof Object** containing the code,
parameters, result, execution environment, SHA-256 hash, Ed25519 signature, and node identity.

### 3 — Value Engine
Automatically detects hidden economic value from the canonical transaction stream.

| Detector | What it finds |
|---|---|
| `duplicate_payment` | Same vendor + similar amount within 30-day window |
| `unused_subscription` | Recurring charges with no usage signal |
| `cost_anomaly` | Transactions above the IQR statistical fence for their vendor |
| `cloud_waste` | Dev environments, egress overcharges, underutilised reservations |
| `tax_credit` *(roadmap)* | Eligible R&D, innovation, and employment credits |
| `public_grant` *(roadmap)* | Matching grant programmes by activity and geography |
| `renegotiable_contract` *(roadmap)* | Contracts above market rate based on spend benchmarks |
| `telecom_overcharge` *(roadmap)* | Line charges inconsistent with contracted rates |
| `unused_license` *(roadmap)* | Software seats with no login activity |

Each detection produces a **Finding** with type, estimated amount, confidence, evidence, and recommended actions.

### 4 — Proof of Value Creation (PVC)
When a Finding is actually recovered, it becomes a verifiable record:
```
Finding (origin)
  + Execution proof (CPO)
  + Recovery proof (documents / on-chain data)
  + Recovered amount
  + Beneficiary
  + Timestamp + Signature
= PVC
```

---

## Quick start

```bash
git clone https://github.com/haynbroit-alt/cpo.git && cd cpo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

### Ingest transactions

```bash
curl -X POST http://localhost:8000/sios/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "source": "csv",
    "data": [
      {"date":"2024-01-15","amount":299.00,"vendor":"Slack","description":"Slack Pro"},
      {"date":"2024-02-15","amount":299.00,"vendor":"Slack","description":"Slack Pro"},
      {"date":"2024-01-20","amount":1250.00,"vendor":"AWS","description":"EC2 dev-server"},
      {"date":"2024-01-21","amount":1250.00,"vendor":"AWS","description":"EC2 dev-server"}
    ]
  }'
```

### Run detection

```bash
curl -X POST http://localhost:8000/sios/detect \
  -H "Content-Type: application/json" -d '{}'

# → {"new_findings": 2, "summary": {"total_estimated_amount": 1549.0, ...}}
```

### Retrieve a Finding

```bash
curl http://localhost:8000/sios/finding/<finding_id>

# → {"type": "duplicate_payment", "estimated_amount": 1250.0, "confidence": 0.95, ...}
```

### Prove a computation (Proof Protocol)

```bash
curl -X POST http://localhost:8000/prove \
  -H "Content-Type: application/json" \
  -d '{"world":"symbolic","claim":"duplicate AWS charge confirmed","code":"print(1250.0 * 2)"}'
```

### Record a recovery (PVC)

```bash
curl -X POST http://localhost:8000/sios/recover \
  -H "Content-Type: application/json" \
  -d '{
    "finding_id": "<finding_id>",
    "recovered_amount": 1250.00,
    "beneficiary": "acme-corp",
    "cpo_id": "<cpo_id>",
    "notes": "Duplicate AWS charge refunded by vendor"
  }'
```

---

## Full API

### SIOS Value Engine

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/sios/ingest` | Ingest JSON transaction array |
| `POST` | `/sios/ingest/csv` | Ingest CSV file upload |
| `POST` | `/sios/normalize` | Return canonical form of transactions |
| `POST` | `/sios/detect` | Run all detectors → Findings |
| `GET` | `/sios/finding/{id}` | Retrieve a Finding |
| `GET` | `/sios/findings` | List findings (filter by status, type) |
| `POST` | `/sios/recover` | Record a recovery → mint a PVC |
| `GET` | `/sios/pvc/{id}` | Retrieve a PVC |
| `GET` | `/sios/leaderboard` | PVCs ranked by recovered amount |

### Proof Protocol

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/prove` | Execute code, return signed CPO |
| `POST` | `/ask` | NL question → code → CPO |
| `GET` | `/verify/{hash}` | Re-execute + verify CPO |
| `GET` | `/cpo/{id}` | Retrieve CPO |
| `GET` | `/ledger` | Browse append-only ledger |
| `GET` | `/node` | Node identity + stats |
| `POST` | `/attest/{hash}` | Peer attestation |
| `GET` | `/cpo/{id}/attestations` | Quorum state |

---

## Integrations

```bash
pip install langchain-cpo   # LangChain callback + chains
pip install dspy-cpo        # DSPy module + predict wrapper
```

→ [`integrations/`](integrations/)

---

## AXIOM — economic layer

AXIOM is the agent scoring and capital allocation protocol built on top of PVC history.

```
AxiomScore(a) = PVCS_cumulative^α · R_identity^β · R_strategy^γ · (1 + VaR)^{-δ}
```

Used to: prioritise agents · allocate budgets · distribute rewards · compare performance.

→ [`axiom/`](axiom/)

---

## Business model

| Model | Description |
|---|---|
| Performance audit | Commission on amounts recovered |
| Enterprise subscription | Continuous monitoring |
| API access | Pay-per-call for integrators |
| Marketplace | Revenue share with agent developers |
| Enterprise private deploy | On-premise + compliance |

---

## Roadmap

**Phase 1 (0–6 months)**
- [x] Proof Protocol (CPO) node — live on Render
- [x] LangChain + DSPy adapters
- [x] SIOS Core (ingestion + normalisation)
- [x] Value Engine — duplicate, subscription, anomaly, cloud detectors
- [ ] PyPI publish (`langchain-cpo`, `dspy-cpo`)
- [ ] PDF / Excel ingestion (PaddleOCR)

**Phase 2 (6–12 months)**
- [ ] Connectors: Stripe, Pennylane, Sage, QuickBooks, Qonto, AWS, Azure
- [ ] Continuous monitoring (scheduled detection)
- [ ] Agent marketplace (submit + publish custom detectors)
- [ ] Public ledger explorer

**Phase 3 (12–24 months)**
- [ ] PVC on-chain anchoring
- [ ] AXIOM reputation + scoring
- [ ] Automatic capital allocation
- [ ] LlamaIndex + OpenTelemetry adapters

**Phase 4 (24 months+)**
- [ ] Third-party agent ecosystem
- [ ] Open proof standard (multi-organisation)
- [ ] Private enterprise deployments

---

## Research

- Proof Protocol formal treatment → [`paper/proof_protocol.tex`](paper/proof_protocol.tex)
- AXIOM white paper → [`axiom/whitepaper/axiom_v1.tex`](axiom/whitepaper/axiom_v1.tex)

---

## Project layout

```
sios/
├── core/
│   ├── models.py        # CanonicalTransaction, Finding, PVC
│   └── ingestion.py     # CSV / JSON / Stripe adapters
└── value_engine/
    ├── base.py          # BaseDetector interface
    ├── engine.py        # ValueEngine orchestrator
    └── detectors/       # duplicate_payment, unused_subscription, cost_anomaly, cloud_waste

app/                     # Proof Protocol FastAPI node
integrations/            # langchain-cpo, dspy-cpo
axiom/                   # AXIOM white paper + formal spec
benchmarks/              # Latency + determinism suite
paper/                   # Proof Protocol research paper
```

---

## License

MIT
