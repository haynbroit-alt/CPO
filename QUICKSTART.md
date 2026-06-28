# SIOS Quickstart

> Find hidden financial losses in your data in under 2 minutes.

---

## Install

```bash
pip install sios
```

Or from source:

```bash
git clone https://github.com/haynbroit-alt/CPO.git
cd CPO
pip install -e .
```

---

## Run your first audit

```bash
sios run examples/sample.csv
```

Expected output:

```
────────────────────────────────────────────────────
  SIOS Audit — sample.csv
  30 transactions analyzed
────────────────────────────────────────────────────

  [Unused subscription]    3,588 EUR  conf: 80%
  AWS recurring charges across 3 months

  [Cost anomaly]           7,650 EUR  conf: 63%
  AWS spike vs. baseline (Feb 14)

  [Cloud waste]            1,350 EUR  conf: 70%
  3 development environments running 24/7

────────────────────────────────────────────────────
  Estimated recoverable: 12,588 EUR
  Findings: 3
────────────────────────────────────────────────────
```

---

## Python API

```python
from sios import SIOS

agent = SIOS()
result = agent.run("data/transactions.csv")

print(f"Estimated savings: {result.estimated_savings:,.0f} {result.currency}")

for finding in result.findings:
    print(f"  [{finding.type.value}] {finding.title} — {finding.estimated_amount}")
```

---

## Input format

CSV with these columns (order doesn't matter):

```csv
date,amount,currency,vendor,description
2024-01-15,299,EUR,Slack,Slack Pro subscription
2024-02-15,299,EUR,Slack,Slack Pro subscription
2024-01-20,1250,EUR,AWS,EC2 instance
```

Minimum required: `date`, `amount`, `vendor`

---

## What SIOS detects

| Type | Description |
|---|---|
| `duplicate_payment` | Same vendor + amount within 30 days |
| `unused_subscription` | Recurring charges with no counterpart |
| `cost_anomaly` | Statistically abnormal spend (IQR) |
| `cloud_waste` | Dev environments, idle resources |

---

## Export results

```bash
# JSON
sios detect examples/sample.csv --format json > report.json

# CSV
sios detect examples/sample.csv --format csv > report.csv
```

---

## Generate a verifiable proof (optional)

```bash
sios prove examples/sample.csv --node https://your-sios-node.onrender.com
```

Output:

```
Generating proofs via https://your-sios-node.onrender.com ...

  AWS subscription anomaly             CPO: 3f8a21c9b7...
  Duplicate Slack payment              CPO: 9d1e4507a2...
  Dev environment cloud waste          CPO: c2f6bb0814...

3 proofs generated.
```

Each CPO is a cryptographically signed, reproducible record of the finding.

---

## More commands

```bash
sios run    file.csv              # Full audit with formatted output
sios detect file.csv              # Detection only
sios detect file.csv --format json  # JSON output
sios prove  file.csv              # Audit + generate CPO proofs
sios export file.csv --out report.json  # Save to file
```

---

## Why SIOS

Most companies lose money silently:
- Forgotten SaaS subscriptions
- Duplicate vendor billing
- Cloud environments running 24/7
- One-time spikes never investigated

SIOS finds these losses automatically and generates a verifiable proof of the result — so you can share it, audit it, or use it to negotiate with vendors.
