# SIOS — Financial Anomaly Detection + Audit Proof

> Detect financial inefficiency patterns in your transaction data. Every finding is probabilistically scored and cryptographically signed.

```
pip install sios
sios run transactions.csv
```

```
────────────────────────────────────────────────────────
  SIOS Audit — transactions.csv
  312 transactions · 6 months
────────────────────────────────────────────────────────

  [Cloud waste]                   HIGH · conf: 81%
  AWS — non-production environments running continuously
  Observed: €12,600 over 6 months
  Estimated savings: €1,260 – €3,780 / year

  [Unused subscription]         MEDIUM · conf: 62%
  Slack Pro — recurring charges, no usage correlation
  Observed: €1,794 over 6 months
  Estimated savings: €90 – €360 / year

  [Cost anomaly]                MEDIUM · conf: 58%
  AWS spike — €8,900 on 2024-01-15, no recurrence
  Observed: single event · signal for investigation

  [Duplicate payment]             HIGH · conf: 94%
  Vendor: Datadog · same amount billed twice (Jan 8–9)
  Observed: €1,195 · recoverable in full

────────────────────────────────────────────────────────
  Quantified estimate: €2,545 – €5,335
  Signals (more data needed): 1
  Findings: 4 · CPO: a83f2c91d4e7...
────────────────────────────────────────────────────────
```

**One dataset → one audit → one verifiable proof.**

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

## Trust tiers

Results are scored by a trust engine that evaluates dataset size, signal consistency, and temporal coverage:

| Trust tier | Dataset | Output |
|---|---|---|
| **LOW** | < 50 transactions | Signal only — pattern detected, no € estimate |
| **MEDIUM** | 50–200 transactions | Range estimate — low/high confidence interval |
| **HIGH** | 200+ transactions | Quantified estimate — statistically grounded |

**Important:** SIOS outputs are probabilistic pattern detections, not verified financial statements. They do not replace an accountant or a legal audit. Use them as a starting point for investigation.

---

## What SIOS detects

| Finding type | Description |
|---|---|
| `duplicate_payment` | Same vendor + similar amount within 7 days |
| `unused_subscription` | Recurring SaaS charges detected as a pattern |
| `cost_anomaly` | Statistically abnormal spend vs. baseline for that vendor |
| `cloud_waste` | Cloud spending patterns indicating inefficiency |

Each finding includes: **trust tier**, **estimate range** (MEDIUM/HIGH), **observed value**, **observation period**, **evidence snapshot**, and **recommended actions**.

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

print(f"Quantified savings: {result.estimated_savings:,.0f} {result.currency}")

for finding in result.findings:
    tier = finding.trust_tier   # "LOW" | "MEDIUM" | "HIGH"
    if tier == "LOW":
        print(f"  [{finding.type.value}]  Signal only — {finding.title}")
    else:
        print(f"  [{finding.type.value}]  {finding.estimate_low:.0f}–{finding.estimate_high:.0f} {finding.currency}  [{tier}]")
        print(f"  {finding.title}")
```

### AuditResult fields

| Field | Type | Description |
|---|---|---|
| `findings` | `List[Finding]` | Detected anomalies, ordered by trust then amount |
| `estimated_savings` | `float` | Total recoverable (MEDIUM + HIGH trust only) |
| `currency` | `str` | Currency code (`EUR`, `USD`, …) |
| `dataset_rows` | `int` | Number of transactions analyzed |
| `summary` | `dict` | Breakdown by finding type |

### Finding fields (v2)

| Field | Type | Description |
|---|---|---|
| `trust_tier` | `str` | `"LOW"` / `"MEDIUM"` / `"HIGH"` |
| `trust_score` | `int` | 0–100 composite score |
| `estimate_low` | `float?` | Lower bound of savings range |
| `estimate_high` | `float?` | Upper bound of savings range |
| `observed_value` | `float?` | Total spend observed in dataset |
| `observed_period` | `str?` | e.g. `"6 months"` |
| `confidence` | `float` | 0.0–1.0 (derived from trust_score) |

---

## Cloud connectors

### AWS Cost Explorer

Pull your AWS billing data directly — no CSV export needed:

```bash
pip install sios[aws]

sios aws --days 90
sios aws --profile production --days 60 --save aws_costs.csv
```

Requires IAM permission `ce:GetCostAndUsage`.

### Stripe

Pull charges and subscriptions, detect duplicate billing and subscription drift:

```bash
pip install sios[stripe]

export STRIPE_API_KEY=sk_live_...
sios stripe --days 90
sios stripe --api-key sk_live_... --save stripe_charges.csv
```

---

## Verifiable proofs (CPO)

Every audit generates a **CPO (Computational Proof Object)** — a SHA-256 fingerprint of all inputs, outputs, and findings. The proof is:

- **Content-addressed** — SHA-256 hash of inputs + outputs
- **Reproducible** — re-run detection on the same file, get the same proof
- **Shareable** — one URL to share with your finance team, external auditor, or vendor

```bash
sios prove transactions.csv --node https://your-sios-node.onrender.com
```

```
CPO: a83f2c91d4e7b0f3...
Verified: https://your-sios-node.onrender.com/verify/a83f2c91d4e7b0f3
```

The CPO is the differentiating feature: **other tools detect anomalies; SIOS proves the detection is reproducible**.

---

## Export

```bash
sios detect transactions.csv --format json > report.json
sios detect transactions.csv --format csv  > report.csv
sios export transactions.csv --out report.json
```

---

## Architecture

```
  Input (CSV · JSON · Stripe · AWS)
          │
          ▼
  ┌─────────────────────┐
  │  Ingestion layer    │  Transaction normalization → canonical model
  └─────────────────────┘
          │
          ▼
  ┌─────────────────────┐
  │  Value Engine       │  Pattern detection pipeline (deterministic)
  │  4 detectors        │  duplicate · subscription · anomaly · cloud
  └─────────────────────┘
          │
          ▼
  ┌─────────────────────┐
  │  Trust Engine       │  Score each finding: LOW / MEDIUM / HIGH
  │  (anti-hallucin.)   │  Range estimates, no extrapolation on thin data
  └─────────────────────┘
          │
          ▼
  ┌─────────────────────┐
  │  Proof Protocol     │  SHA-256 · append-only ledger · verify URL
  │  (CPO)              │  Reproducible, shareable audit trail
  └─────────────────────┘
```

**Design principles:**
- **Honest by default** — LOW trust findings never show € amounts
- **Deterministic** — same input always produces the same findings and proof
- **No double-counting** — each transaction claimed by at most one finding
- **Modular** — each detector is an independent plugin

---

## CLI reference

```bash
sios run    file.csv                      # Full audit, formatted output
sios detect file.csv                      # Detection only, table format
sios detect file.csv --format json        # JSON output
sios detect file.csv --format csv         # CSV output
sios prove  file.csv --node <url>         # Audit + generate CPO proof
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

## What SIOS is (and isn't)

SIOS is a **probabilistic anomaly detection system** with a **verifiable audit trail**.

It is good at:
- Surfacing patterns in transaction data that warrant investigation
- Generating reproducible, shareable proof of what was detected
- Giving finance teams a fast starting point for cost reviews

It is not:
- A replacement for a human auditor or accountant
- A system that verifies whether charges are contractually valid
- A guarantee of recovered amounts

The trust engine is explicit about this: if data is insufficient, SIOS says so rather than inventing numbers.

---

## Use cases

| User | How they use SIOS |
|---|---|
| **Finance team** | Monthly audit of card statements and cloud bills |
| **Engineering** | Post-incident cost review after infrastructure changes |
| **Startup CFO** | SaaS spend audit before a funding round |
| **Accountant / firm** | Client cost optimization as a service |
| **SaaS vendor** | Embed anomaly detection into your own product |

---

## Roadmap

- [x] CLI (`sios run`, `detect`, `prove`, `export`)
- [x] Python SDK (`from sios import SIOS`)
- [x] AWS Cost Explorer connector
- [x] Stripe connector
- [x] Trust engine (LOW / MEDIUM / HIGH tiers, range estimates)
- [x] Verifiable proofs (CPO)
- [x] PyPI package (`pip install sios`)
- [ ] PDF / bank statement ingestion
- [ ] Qonto, Pennylane, QuickBooks connectors
- [ ] Continuous monitoring (scheduled detection)
- [ ] Custom detector plugin API

---

## License

MIT — free to use, modify, and embed in commercial products.

---

*SIOS detects financial inefficiency patterns in structured transaction data. Results are probabilistic estimates and do not constitute verified financial statements.*
