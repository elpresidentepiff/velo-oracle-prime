# VELO ACCA Lane Proposal V1

## Executive Summary

VÉLØ should add a dedicated accumulator-analysis lane instead of treating accas as a by-product of single-runner scoring.

This lane should not think like `VP30`, `MDS`, or `CASHRUN`.

- `VP30` answers: is this runner live enough to matter?
- `MDS` answers: what is the market shape doing?
- `CASHRUN` answers: is there hidden handicap intent?
- `ACCA_LANE` should answer: which runners belong together in a realistic accumulator chain?

The lane should therefore be built as a chain-quality system, not a generic multi-pick printer.

Initial release posture:

```text
SHADOW_OPERATOR_ONLY
NO_LIVE_SCORING_CHANGE
NO_STAKING
NO_ROUTER_CHANGE
NO_BETFAIR
NO_TELEGRAM_BETTING_LANGUAGE
NO_AUTOMATIC_EXECUTION
```

---

## Why This Lane Should Exist

Recent VÉLØ result days showed that multi-win clustering is real and that some race days naturally support doubles, trebles, and longer ladders.

At the moment, that edge is informal:

- humans eyeball the VP30 card
- humans blend MDS by feel
- humans sometimes add CASHRUN intuition
- humans then guess which legs fit together

That is good enough for discovery, but not good enough for a durable VÉLØ lane.

The acca lane should formalize:

- whether the day is even suitable for accumulator chaining
- which horses are acceptable acca legs
- which horses are trap legs
- which combinations are coherent rather than random
- when a day should be declared `NO_ACCA_DAY`

---

## Core Doctrine

The acca lane must think in two layers:

1. `LEG_QUALITY`
2. `COMBO_QUALITY`

A horse can be a good single-runner signal and still be a bad accumulator leg.
An acca lane must therefore evaluate both the leg and the chain.

It must also classify the race day before suggesting folds.

---

## Proposed Lane Identity

### Lane name

`ACCA_LANE_V1`

### Position in the VÉLØ stack

```text
Racing API      = structure
Racing Post     = intent
VP              = probability
MDS             = market shape / deception
CASHRUN         = handicap-plot / setup intent
ACCA_LANE       = chain quality / leg compatibility
```

### Status on build

```text
SHADOW_OPERATOR_ONLY
PROPOSED_ONLY
EVIDENCE_REQUIRED
FORWARD_TEST_REQUIRED
```

---

## Day Regime Model

Before any fold is built, the lane should classify the day:

- `ACCA_DAY_STRONG`
- `ACCA_DAY_PLAYABLE`
- `ACCA_DAY_THIN`
- `NO_ACCA_DAY`

This matters because some days contain real chain density and some do not.

If the day is `NO_ACCA_DAY`, the lane should say so and suppress longer-chain output.

---

## Leg Role Taxonomy

Each candidate leg should be assigned one primary role:

- `BANKER`
- `GLUE`
- `BOOSTER`
- `WILDCARD`
- `TRAP`
- `BLOCKED`

### Banker

High-trust leg.

Typical profile:

- VP30 live
- Tier A, or strongest clean Tier B
- strong place/frame support
- no major blocker
- no clear decoy signal

### Glue

Stable leg that helps hold an acca together without needing to be the star.

Typical profile:

- acceptable VP
- strong enough place support
- lower volatility than a price-chasing leg
- not a decoy

### Booster

Leg that increases payout without collapsing realism.

Typical profile:

- mid-price or bigger price
- still supported by VÉLØ logic
- ideally backed by MDS, CASHRUN, or industry confirmation

### Wildcard

Interesting but unstable leg.

Typical profile:

- partial convergence only
- allowed only in more aggressive ladders
- never used in the cleanest core chain

### Trap

Leg to avoid in natural accas.

Typical profile:

- `HIGH_DECOY_RISK`
- `DX_GOING_BLOCKER`
- `DX_NO_SIGNAL`
- weak margin
- unstable support
- unresolved or contradictory source state

### Blocked

Cannot be considered for the lane.

Typical profile:

- missing critical metadata
- unresolved runner state
- non-runner / late uncertainty
- data integrity failure

---

## Inputs

The acca lane should consume existing VÉLØ intelligence rather than inventing a separate model.

### VÉLØ live verdict inputs

From `velo_prime_verdicts` / same-day operator lanes:

- `velo_prime_prob`
- `decision_tier`
- `place_prob`
- `market_deception_score`
- `improvement_score`
- `candidate_execution_allowed` as visibility only
- blocker and suppressor labels

### CASHRUN inputs

From `cashrun_detector.py` when available:

- `cashrun_class`
- `final_cashrun_score`
- `confidence_level`
- source completeness flags

### Racing API enrichment inputs

Shadow-only context:

- trainer course
- trainer distance
- jockey course
- jockey distance
- trainer/jockey partnership

These should not force a leg into the chain, but can support or suppress confidence.

### Racing Post / industry inputs

Parsed industry-selection lanes:

- `SPOTLIGHT`
- `POSTDATA`
- `TOPSPEED`
- `RP RATINGS`
- later: Timeform if parsed cleanly

### Race-structure inputs

- course
- off_time
- race_name
- field size
- handicap / non-handicap
- race volatility
- non-runner exposure
- time ordering across the card

---

## Scoring Model Proposal

### Layer 1: Leg Score

The lane should compute a `leg_score` that answers:

`Should this horse be included in any realistic acca chain?`

Proposed first-pass contribution model:

- live VP / confidence spine: `30`
- place / frame support: `20`
- MDS / market-shape support: `10`
- CASHRUN boost: `10`
- industry confirmation: `10`
- tier cleanliness / no blocker state: `20`

Negative adjustments:

- decoy risk
- going blocker
- weak margin
- missing or contradictory source state
- low-confidence CASHRUN status
- unstable race setup

### Layer 2: Combo Score

The lane should compute a `combo_score` that answers:

`Do these legs belong together as a chain?`

Combo features should include:

- presence of at least one `BANKER`
- number of `TRAP` legs must be zero
- capped number of `BOOSTER` legs by fold size
- cumulative place support
- cumulative VP floor
- chain cleanliness
- absence of over-stacked fragility
- payout profile that is not pure short-price mush and not pure longshot fantasy

---

## Fold Construction Rules

These are starting rules, not final law.

### 2-fold

- 2 `BANKER`s
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

- allowed only on `ACCA_DAY_STRONG`
- never forced
- no `TRAP`
- no `BLOCKED`
- limited booster count

If the day is only `ACCA_DAY_THIN`, the lane should suppress 5-fold and 6-fold output.

---

## Trap Logic

The lane should explicitly return a trap list, not just a suggested chain.

Trap labels can be driven by:

- `HIGH_DECOY_RISK`
- `DX_GOING_BLOCKER`
- `DX_NO_SIGNAL`
- weak margin state
- unstable field / race setup
- low-confidence or low-source CASHRUN
- conflicting VÉLØ vs industry signals

This matters because a realistic acca system is as much about rejecting bad legs as finding attractive ones.

---

## Proposed Artifacts

### Runtime scripts

- `scripts/acca_detector.py`
- `scripts/acca_results_audit.py`

### Documentation

- `docs/engineering/VELO_ACCA_LANE_PROTOCOL_V1.md`

### Output files

- `data/acca_lane_report_YYYY_MM_DD.md`
- `data/acca_lane_report_YYYY_MM_DD.json`
- `data/acca_lane_report_YYYY_MM_DD.csv`
- `data/acca_operator_card_YYYY_MM_DD.md`

---

## Proposed Output Shape

### Operator card

The operator card should show:

- day status
- strongest 2-fold
- strongest 3-fold
- strongest 4-fold
- controlled 5-fold
- speculative 6-fold
- trap legs to avoid
- rationale for chain construction

Per leg:

- horse
- course
- off_time
- role
- VP
- MDS
- place_prob
- CASHRUN class if present
- industry confirmation count
- blocker flags

### Full report

The full report should show:

- day regime classification
- all candidate legs ranked
- rejected legs and why
- chain score breakdown
- fold-by-fold reasoning
- source completeness notes

---

## Validation Plan

The lane should be tested in shadow first using known dates with:

- VÉLØ verdicts
- race results
- Racing Post merged data
- industry selections

Suggested initial replay set:

- `2026-05-06`
- `2026-05-07`
- then a rolling 10-20 day replay set

Metrics to track:

- 2-fold hit rate
- 3-fold hit rate
- 4-fold hit rate
- 5-fold hit rate
- 6-fold hit rate
- ROI by fold size
- average cumulative price
- number of days correctly classified as `NO_ACCA_DAY`
- comparison against:
  - naive top-VP chains
  - naive VP30 chains
  - Spotlight-led chains
  - Postdata-led chains
  - industry consensus chains

---

## Tomorrow Test Flow

Once built, the intended daily operator workflow is:

1. ingest tomorrow's Racing Post file
2. parse industry selections
3. run CASHRUN
4. load same-day VÉLØ verdicts
5. run `ACCA_LANE_V1`
6. output the acca operator card and full report

This gives the lane a real race-day operating loop without touching live scoring.

---

## Hard Safety Contract

```text
NO change to velo_prime_prob
NO change to SQPE
NO change to ensemble weights
NO change to decision_tier
NO change to router
NO staking
NO Betfair integration
NO live execution
NO Telegram betting alerts
SHADOW / OPERATOR ONLY
```

---

## Recommendation

The acca detector should be built.

But it should be built as:

- a chain-quality lane
- a day classifier
- a trap-leg suppressor
- a shadow operator tool

It should not be built as:

- a brute-force combination printer
- a staking engine
- a betting bot
- a live-control lane

That is the cleanest path to turning today's manual acca intuition into a durable VÉLØ intelligence layer.
