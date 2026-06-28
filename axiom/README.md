# AXIOM v1.0 — Autonomous Value Protocol

**A decentralised economic protocol for allocating capital to autonomous agents via verifiable proof of value creation.**

---

## Core Idea

> Axiom does not reward revenue. Axiom rewards net value created.

The fundamental unit is the **Proof of Value Creation (PVC)** — a cryptographically attested, risk-adjusted record that an agent produced genuine economic value in a verifiable execution context.

---

## Architecture

```
Couche 1 — Agents          AgentID + Stake + PVC History + Reputation
Couche 2 — Validation      Submitted → Primary Validated → Challenge → Finalised
Couche 3 — Réputation      R_identity (longevity) × R_strategy (performance)
Couche 4 — Allocation      AxiomScore → proportional capital allocation
Couche 5 — Gouvernance     Parameters only; proof history is immutable
```

---

## Key Formulas

**Net Value Created**
```
NVC = (V_final - V_initial) - C · r_f · τ
```

**PVC Score (risk-adjusted)**
```
PVCS = NVC / (C · σ · √τ)
```

**AxiomScore**
```
AS(a) = PVCS_cumulative^α · R_id^β · R_strat^γ · (1 + VaR)^{-δ}
```

**Capital Allocation**
```
C_a = C_total · AS(a)^η / Σ_b AS(b)^η
```

**Protocol Value Efficiency**
```
PVE = Σ NVC / Σ C_allocated     (must remain > 0)
```

---

## Formal Specification

- Full white paper: [`whitepaper/axiom_v1.tex`](whitepaper/axiom_v1.tex)
- Compact reference: [`spec/formal_spec.md`](spec/formal_spec.md)

Key theorems proven in the white paper:
1. **Fraud Irrationality** — fraud is economically irrational iff `stake > G(1-p)/p`
2. **Allocation Convergence** — AxiomScore converges to a unique fixed point under stationary agents
3. **PVE Positivity** — the pool maintains positive returns under the fraud-irrationality regime

---

## Relation to Proof Protocol / CPO

| Layer | Protocol | Question answered |
|---|---|---|
| Execution | [Proof Protocol / CPO](../README.md) | Was this computation correct? |
| Economics | AXIOM | Was this computation valuable? |

A PVC's `π` field can point to a CPO, composing both layers without structural dependency.

---

## MVP

- Crypto trading agents only
- On-chain profits as PVC values
- 3-validator primary validation
- 48-hour Challenge Window
- Single capital pool, daily rebalancing
- Objective: demonstrate `PVE > 0` over 90 days

---

## Status

White paper draft — pre-implementation. Seeking feedback and MVP co-builders.
