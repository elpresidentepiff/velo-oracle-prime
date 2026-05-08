# VELO ACCA Lane Protocol V1

## Lane Identity

```text
ACCA_LANE_V1
SHADOW_OPERATOR_ONLY
EVIDENCE_REQUIRED
FORWARD_TEST_REQUIRED
```

The ACCA lane is a chain-quality intelligence layer.

It does not exist to print combinations blindly.
It exists to determine whether the day supports coherent operator chains and which legs belong in them.

---

## Stack Position

```text
Racing API      = structure
Racing Post     = intent
VP              = probability
MDS             = market shape
CASHRUN         = handicap / setup intent
ACCA_LANE       = chain quality / leg compatibility
```

---

## Day Regime

The lane must classify the card before building folds:

- `ACCA_DAY_STRONG`
- `ACCA_DAY_PLAYABLE`
- `ACCA_DAY_THIN`
- `NO_ACCA_DAY`

This is mandatory.

If the day is not naturally chainable, VÉLØ must say so.

---

## Leg Roles

Each candidate leg must be classified as one of:

- `BANKER`
- `GLUE`
- `BOOSTER`
- `WILDCARD`
- `TRAP`
- `BLOCKED`

### BANKER

High-trust leg with live support and low contradiction risk.

### GLUE

Stable leg that helps a chain hold together.

### BOOSTER

A stronger-upside leg that remains coherent inside the chain.

### WILDCARD

Interesting but less stable leg, acceptable only in controlled contexts.

### TRAP

Leg with a meaningful reason to avoid chain inclusion.

### BLOCKED

Leg disallowed due to missing metadata, unresolved state, or hard integrity issues.

---

## Inputs

The lane consumes existing VÉLØ intelligence only.

### Core live inputs

- `velo_prime_prob`
- `decision_tier`
- `place_prob`
- `market_deception_score`
- `improvement_score`
- blocker and suppressor flags
- `candidate_execution_allowed` as visibility only

### Optional context inputs

- CASHRUN class and score when available
- Racing API enrichment when available
- Spotlight / Postdata / industry selections when available
- race structure:
  - course
  - off_time
  - race_name
  - race type
  - field size
  - volatility clues

Optional sources must never be hallucinated.
If missing, they are marked missing optional.

---

## Leg Score Model

### Positive contribution model

- VP / confidence spine: `30`
- place / frame support: `20`
- MDS / market shape support: `10`
- CASHRUN: `10`
- industry confirmation: `10`
- tier cleanliness / no blockers: `20`

### Negative adjustments

Subtract for:

- trap labels
- decoy risk
- going blockers
- no-signal blockers
- weak-margin states
- contradictory source state
- missing critical metadata
- unresolved optional context that lowers confidence

The leg score must be bounded and interpretable.

---

## Combo Score Model

The combo score evaluates whether legs belong together.

Required combo rules:

- at least one `BANKER`
- zero `TRAP` legs
- capped booster count
- cumulative VP floor
- cumulative frame support
- chain cleanliness
- no over-stacked fragility

The lane must prefer coherent shadow chains over random high-score bundles.

---

## Fold Construction Rules

### 2-fold

- `BANKER + BANKER`
- or `BANKER + BOOSTER`

### 3-fold

- at least 2 `BANKER`s
- max 1 `BOOSTER`

### 4-fold

- at least 2 `BANKER`s
- at least 1 `GLUE`
- max 1 `BOOSTER`

### 5-fold

- at least 3 `BANKER`s
- max 1 `BOOSTER`
- no `WILDCARD`

### 6-fold

- only on `ACCA_DAY_STRONG`
- never forced

---

## Trap Logic

The lane must explicitly detect trap legs.

Trap reasons include:

- `HIGH_DECOY_RISK`
- `DX_GOING_BLOCKER`
- `DX_NO_SIGNAL`
- weak margin
- unresolved metadata
- contradictory source state
- low-confidence CASHRUN
- VÉLØ / industry conflict

Trap legs are a first-class output of the lane.

---

## Validation Plan

Replay and forward-test are both required.

### Initial replay dates

- `2026-05-06`
- `2026-05-07`

Then expand to a rolling 10-20 day sample.

### Comparison baselines

- naive top-VP chains
- naive VP30 chains
- Spotlight-led chains
- Postdata-led chains
- industry-consensus chains

### Metrics

Track by fold size:

- hit rate
- ROI
- average cumulative price
- day-regime accuracy
- `NO_ACCA_DAY` correctness

---

## Safety Contract

```text
NO change to velo_prime_prob
NO SQPE change
NO ensemble weight change
NO decision_tier change
NO router change
NO staking
NO Betfair
NO live execution
NO Telegram betting alerts
NO "bet this" language
SHADOW / OPERATOR ONLY
```

The lane is judged only by replay and forward-test evidence.
It is blocked from live promotion.
