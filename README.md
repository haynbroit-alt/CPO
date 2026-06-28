# SIOS — Financial Audit Engine

> Detect hidden financial losses in your transaction data. Every finding is reproducible and cryptographically signed.

```
pip install sios
sios run examples/sample.csv
```

```
────────────────────────────────────────────────────────
  SIOS Audit — sample.csv
  21 transactions analyzed
────────────────────────────────────────────────────────

  [Duplicate payment]        1,195 EUR  conf: 95%
  Duplicate AWS charge — EC2 Production (Feb)

  [Cost anomaly]             7,650 EUR  conf: 72%
  AWS spike vs. baseline — load test environment (Feb 14)

  [Unused subscription]        588 EUR  conf: 80%
  GitHub Teams — 3 recurring charges, no usage signal

  [Cloud waste]                522 EUR  conf: 65%
  EC2 dev environments running 24/7 across 3 months

────────────────────────────────────────────────────────
  Estimated recoverable: 31,121 EUR
  Findings: 12
────────────────────────────────────────────────────────
```

**One dataset → one audit → one proof.**

---

## Install

```bash
pip install sios
```

Requires Python 3.11+. Zero configuration.

---

## Quickstart

```bash
# Run a full financial audit
sios run transactions.csv

# JSON output for downstream processing
sios detect transactions.csv --format json

# Export to file
sios export transactions.csv --out report.json
```

**Time-to-value: under 2 minutes from install to first findings.**

---

## What SIOS detects

| Finding type | Description | Typical recovery |
|---|---|---|
| `duplicate_payment` | Same vendor + similar amount within 7 days | Full refund |
| `unused_subscription` | Recurring charges with no counterpart activity | Cancel or renegotiate |
| `cost_anomaly` | Statistically abnormal spend (IQR fence per vendor) | Investigate + credit |
| `cloud_waste` | Dev/staging environments running continuously | Right-size or terminate |

Each finding includes an **estimated recovery amount**, a **confidence score (0–100%)**, an **evidence snapshot**, and **recommended actions**.

---

## Input format

CSV with these columns (order doesn't matter):

```csv
date,amount,currency,vendor,description
2024-01-15,299,EUR,Slack,Slack Pro subscription
2024-02-15,299,EUR,Slack,Slack Pro subscription
2024-01-20,1250,EUR,AWS,EC2 dev server
```

Minimum required: `date`, `amount`, `vendor`.  
Also accepts JSON. Currency defaults to EUR; detected per-dataset automatically.

---

## Python SDK

```python
from sios import SIOS

agent = SIOS()
result = agent.run("data/transactions.csv")

print(f"Estimated savings: {result.estimated_savings:,.0f} {result.currency}")

for finding in result.findings:
    print(f"  [{finding.type.value}]  {finding.estimated_amount:,.0f} {finding.currency}  conf={finding.confidence:.0%}")
    print(f"  {finding.title}")
    print(f"  {finding.description[:100]}")
```

### AuditResult fields

| Field | Type | Description |
|---|---|---|
| `findings` | `List[Finding]` | Detected anomalies, ordered by amount |
| `estimated_savings` | `float` | Total recoverable across all findings |
| `currency` | `str` | Currency code (`EUR`, `USD`, …) |
| `dataset_rows` | `int` | Number of transactions analyzed |
| `summary` | `dict` | Breakdown by finding type |

---

## Cloud connectors

### AWS Cost Explorer

Pull your AWS billing data directly — no CSV export needed:

```bash
pip install sios[aws]

sios aws --days 90
sios aws --profile production --days 60 --save aws_costs.csv
```

Requires IAM permission `ce:GetCostAndUsage`. Detects idle reservations, dev environment waste, and service-level anomalies.

### Stripe

Pull charges and subscriptions, detect duplicate billing and subscription drift:

```bash
pip install sios[stripe]

export STRIPE_API_KEY=sk_live_...
sios stripe --days 90
sios stripe --api-key sk_live_... --save stripe_charges.csv
```

### Python API — connectors

```python
from sios.connectors.aws import AWSConnector
from sios.connectors.stripe import StripeConnector
from sios.value_engine.engine import ValueEngine

# AWS
transactions = AWSConnector(profile="production").fetch(days=90)
findings = ValueEngine().run(transactions)

# Stripe
transactions = StripeConnector(api_key="sk_live_...").fetch(days=90)
findings = ValueEngine().run(transactions)
```

---

## Verifiable proofs (optional)

Every finding can be signed and submitted to a Proof Protocol node:

```bash
sios prove transactions.csv --node https://your-sios-node.onrender.com
```

```
Generating proofs via https://your-sios-node.onrender.com ...

  AWS duplicate charge confirmed          CPO: 3f8a21c9b7...
  Slack subscription anomaly              CPO: 9d1e4507a2...
  Dev environment cloud waste             CPO: c2f6bb0814...

3 proofs generated.
```

Each **CPO (Computational Proof Object)** is:
- **Cryptographically signed** — Ed25519 signature over the canonical payload
- **Content-addressed** — SHA-256 hash of inputs + outputs
- **Reproducible** — re-execute at any time, get the same result
- **Append-only** — recorded in a tamper-evident ledger

The proof ties the finding to the specific code, data, and environment that produced it — creating an **audit trail** suitable for sharing with finance teams, external auditors, or vendors during dispute resolution.

---

## Export

```bash
# JSON report
sios detect transactions.csv --format json > report.json

# CSV for Excel / BI tools
sios detect transactions.csv --format csv > report.csv

# Save directly
sios export transactions.csv --out report.json
sios export transactions.csv --format csv --out report.csv
```

---

## Architecture

```
  Input (CSV · JSON · Stripe · AWS)
          │
          ▼
  ┌─────────────────────┐
  │  Ingestion layer    │  Transaction normalization → canonical data model
  └─────────────────────┘
          │
          ▼
  ┌─────────────────────┐
  │  Value Engine       │  Rule-based detection pipeline (idempotent, stateless)
  │  4 detectors        │  duplicate · subscription · anomaly · cloud waste
  └─────────────────────┘
          │
          ▼
  ┌─────────────────────┐
  │  Findings           │  amount · confidence · evidence · recommended actions
  └─────────────────────┘
          │
          ▼
  ┌─────────────────────┐
  │  Proof Protocol     │  Ed25519 sign · SHA-256 hash · append-only ledger
  │  (optional)         │  Verifiable, reproducible execution trace
  └─────────────────────┘
```

**Design principles:**
- **Deterministic execution** — same input always produces the same findings
- **Idempotent processing** — running twice on the same dataset returns cached results
- **Modular architecture** — each detector is an independent plugin; add your own
- **Persistent store** — SQLite (default) or Postgres; WAL mode, thread-safe
- **Stateless API** — the FastAPI server layer adds no shared mutable state

---

## CLI reference

```bash
sios run    file.csv                      # Full audit, formatted output
sios detect file.csv                      # Detection only, table format
sios detect file.csv --format json        # JSON output
sios detect file.csv --format csv         # CSV output
sios prove  file.csv --node <url>         # Audit + generate CPO proofs
sios export file.csv --out report.json    # Save to file
sios aws    --days 90                     # Pull from AWS Cost Explorer
sios stripe --days 90                     # Pull from Stripe
```

---

## Install options

```bash
pip install sios              # Core (CLI + Python SDK)
pip install sios[aws]         # + AWS Cost Explorer connector
pip install sios[stripe]      # + Stripe connector
pip install sios[server]      # + FastAPI proof server
pip install sios[all]         # Everything
```

---

## Why SIOS

Most companies lose money silently:

- **Forgotten SaaS subscriptions** — tools nobody uses, renewed automatically
- **Duplicate vendor billing** — the same invoice paid twice in the same cycle
- **Cloud environments running 24/7** — dev and staging never turned off
- **One-time spikes never investigated** — a load test billed at full rate, forever forgotten

SIOS detects these patterns automatically from raw transaction data.  
Every result is backed by a confidence score, an evidence snapshot, and — when you need it — a cryptographic proof that the finding is reproducible and tamper-evident.

**Install, run, recover value.**

---

## Use cases

| User | How they use SIOS |
|---|---|
| **Finance team** | Monthly audit of card statements and cloud bills |
| **Engineering** | Post-incident cost review after infrastructure changes |
| **Startup CFO** | SaaS spend audit before a funding round |
| **Accountant / firm** | Client cost optimization as a service |
| **SaaS vendor** | Embed duplicate billing detection into your own product |

---

## Roadmap

- [x] CLI (`sios run`, `detect`, `prove`, `export`)
- [x] Python SDK (`from sios import SIOS`)
- [x] AWS Cost Explorer connector
- [x] Stripe connector
- [x] Verifiable proofs (CPO)
- [x] PyPI package (`pip install sios`)
- [ ] PDF / bank statement ingestion
- [ ] Qonto, Pennylane, QuickBooks, Sage connectors
- [ ] Continuous monitoring (scheduled detection)
- [ ] Export to PDF audit report
- [ ] Custom detector plugin API

---

## License

MIT — free to use, modify, and embed in commercial products.

---

*SIOS detects financial inefficiencies in structured data. We turn raw transactions into audited savings opportunities.*
