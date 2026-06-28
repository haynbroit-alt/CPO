# AXIOM v1.0 — Formal Specification Reference

## Primitive Types

| Symbol | Type | Description |
|---|---|---|
| `id_a` | bytes32 | Agent public key hash |
| `stake_a` | ℝ≥0 | Collateral deposited |
| `R_id(a,t)` | [0,1] | Identity reputation |
| `R_strat(a,t)` | [0,1] | Strategy reputation |
| `s_a` | S | Current strategy class |

---

## PVC

```
PVC = (id_a, s_a, V0, V1, C, τ, σ, π)
```

| Field | Description |
|---|---|
| `V0, V1` | Observable value at start/end (common numeraire) |
| `C` | Capital allocated by protocol |
| `τ` | Duration = t1 - t0 |
| `σ` | Realised volatility over [t0, t1] |
| `π` | Execution proof (CPO or on-chain attestation) |

---

## Value Metrics

```
NVC(PVC)  = (V1 - V0) - C · r_f · τ
PVCS(PVC) = NVC(PVC) / (C · σ · √τ)
PVE(T)    = Σ_a Σ_i NVC(PVC_i)  /  Σ_a ∫₀ᵀ C_a(t) dt
```

---

## Reputation Updates

```
R_id(a, t+1)   = (1 - λ_id)   · R_id(a, t)   + λ_id   · b_t
R_strat(a,t+1) = (1 - λ_strat)· R_strat(a,t) + λ_strat · Φ(PVCS(PVC_i))

# Strategy switch from s → s':
R_strat'(a) = R_strat(a) · M[s, s']    # M = proximity matrix ∈ [0,1]^|S|×|S|
```

---

## AxiomScore

```
AS(a, t) = [Σ_i PVCS(PVC_i) · exp(-κ(t - t_i))]^α
           · R_id(a, t)^β
           · R_strat(a, t)^γ
           · (1 + VaR_δ(a, t))^(-δ)
```

| Parameter | Role |
|---|---|
| `α` | Performance weight |
| `β` | Identity trust weight |
| `γ` | Strategy mastery weight |
| `δ` | Tail-risk penalty |
| `κ` | Recency decay (half-life = ln2/κ) |

---

## Capital Allocation

```
C_a(t) = C_total(t) · AS(a,t)^η / Σ_b AS(b,t)^η
```

`η ≥ 1`: concentration. `η=1` → proportional. Higher η → winner-takes-more.

---

## Slashing Condition

Fraud is irrational iff:

```
stake_a > G · (1-p) / p
```

where `G` = expected gain from fraud, `p` = detection probability.

---

## MVP Parameters

| Parameter | MVP Value |
|---|---|
| `α` | 1.0 |
| `β` | 0.5 |
| `γ` | 0.0 (disabled, single strategy) |
| `δ` | 0.5 |
| `η` | 1.0 (proportional) |
| `κ` | ln(2)/30 (30-day half-life) |
| `λ_id` | 0.1 |
| `λ_strat` | 0.1 |
| `r_f` | annualised reference rate |
| Rebalancing | daily |
| Challenge Window | 48h |
| Validators per PVC | 3 |

---

## PVC State Machine

```
Submitted → Primary Validated → Challenge Window →
  ├── Finalised  (no valid challenge)
  └── Audited    (challenge raised) →
        ├── Accepted
        └── Rejected (agent slashed)
```

---

## Security Properties

| Attack | Defence |
|---|---|
| Sybil | `R_id = 0` at genesis → zero allocation until history built |
| Fake PVC | Execution proof `π` required; non-forgeable under Ed25519 |
| Reputation laundering | `M[s,s'] ≪ 1` for distant strategy classes |
| Oracle manipulation | On-chain source committed in `π`; disputable |
| Correlation attack | Aggregate allocation to correlated cluster capped at `θ·C_total²` |
| Validator collusion | Requires >⌊|V|/3⌋ colluders; each risks full stake |
