# Midprice Hunter V2 — Research Plan

**Status:** RESEARCH_PENDING  
**Origin:** Midprice delta diagnosis + Race Shape V1 design  
**Classification:** Research plan only. No scoring, routing, or staking changes.

---

## Why V1 Failed to Fix Mid-Price

### V1 architecture (current)
Mid-Price Hunter V1 is a shadow monitor. It watches for races where VELO suppresses a mid-price top pick. It does not change scores or routes. `live_scoring_changed=False`, `execution_allowed=False`.

The V1 concept was: "if we can detect overconfident mid-price picks, suppress them." The delta diagnosis shows this is the wrong frame.

### What the data says

| Finding | Implication |
|---|---|
| Winner visible in 96.6% of misses | Not a coverage or identity failure |
| 51.8% of winners ranked 2nd/3rd | VELO already frames many winners — ranking is the problem |
| Rescue rate 3.4% via sidecars | MDS/improvement can't close a 0.093 average VP gap |
| 0 MDS>0.5 fires in 2-day window | Rare signals don't explain systematic mid-price misses |
| Mean VP delta = 0.093 | Model is materially confident in wrong horse, not just marginally wrong |

### V1 failure modes
1. **Threshold tuning trap:** Raising MDS/improvement thresholds doesn't help when those signals don't fire.
2. **Suppression without replacement:** Suppressing a top pick doesn't tell you who wins instead.
3. **Sidecar spaghetti:** Adding more sidecar filters to a structural problem makes the system opaque without improving accuracy.

---

## V2 Research Hypothesis

**The mid-price winner wins because the race shape disadvantages the top-rated horse, not because the winner is intrinsically better.**

V2 investigates whether race-shape features (pace, class-drop, going, field compression) can identify the subset of mid-price races where the VP ranking is most likely wrong.

This is a **selection filter** research problem, not a scoring change:
- Which mid-price races should VELO avoid picking the top VP horse?
- Which races have race-shape conditions that favour an alternative?

---

## Research Questions

1. Do races with `pace_pressure_count >= 3` (contested pace) have lower top-pick SR?
2. Do races where the 2nd/3rd ranked horse is a class-drop have higher "wrong pick" rates?
3. Is `field_compression` (VP spread) correlated with miss probability?
4. Does `sp_vp_misalign` (market favours horse model doesn't) predict the winner?
5. What is the SR by price band for VELO top picks? Does it collapse in SP 4–6?
6. Do DPT-equivalent data gaps systematically affect which course/race types are missed?

---

## Research Protocol

### Step 1 — Extend the delta corpus

Current corpus: 80 races, 2 days. Need at minimum 20 days for stable findings.

Run `midprice_winner_delta.py` daily after sigma. Corpus grows automatically.

Target: 300+ mid-price miss races before drawing feature-level conclusions.

### Step 2 — Add race-shape features to the delta CSV

Extend `midprice_winner_delta.py` to compute per-race:
- `field_compression` from snapshots (already feasible)
- `midprice_runner_count` (how many runners are in the 3–8.5 zone)
- `winner_sp_rank` (was the winner the cheapest, 2nd cheapest, etc.)
- `top_pick_is_favourite` (flag)
- `sp_vp_rank_corr` (how well SP and VP agree for this race)

### Step 3 — SR analysis by feature quartile

For each feature: bucket races into quartiles, compute top-pick SR per quartile.

If a feature shows >10pp SR difference between top/bottom quartile, it has discriminative power.

### Step 4 — Race-shape suppression candidate test

For races where race-shape flags fire (e.g., `contested_pace=True AND field_compression < 0.15`): what is the top-pick SR?

If SR drops below 15% when race-shape flags fire, that defines a suppression candidate set.

### Step 5 — Alternative pick evaluation

For the suppression candidate set: if we had picked rank=1 or rank=2 instead of rank=0, what would SR be?

If alternative SR > top-pick SR in that subset, V2 has a research basis.

---

## What V2 Is Not

```
V2 is NOT:
  - A new scoring model
  - A new sidecar threshold
  - A direct replacement for VP
  - A live execution engine
  - A staking system

V2 IS:
  - A race-level selection filter
  - A shadow-only research corpus
  - A suppression candidate identifier
  - Evidence for a future race-shape VP modifier
```

---

## Output Artifacts

| Artifact | Path | When |
|---|---|---|
| Extended delta CSV | `data/midprice_winner_deltas.csv` | After each sigma |
| Race-shape features | `data/features/race_shape_features_latest.parquet` | Phase 1 |
| SR-by-feature audit | `data/reports/midprice_sr_by_feature_latest.md` | Phase 2 |
| Suppression candidate report | `data/reports/midprice_suppression_candidates_latest.json` | Phase 3 |
| V2 research summary | `docs/engineering/MIDPRICE_HUNTER_V2_FINDINGS.md` | Phase 4 |

---

## Timelines and Gates

| Milestone | Trigger |
|---|---|
| Phase 1 start | 300+ mid-price miss races in corpus AND operator approval |
| Phase 2 start | Phase 1 features validated — no flatlines |
| Phase 3 start | At least 2 features with >10pp SR lift in quartile analysis |
| V2 live shadow | Operator decision only — never automatic |
| Scoring change | Never without full Gate V3 evidence |

---

## Alignment with Race Shape Model V1

`RACE_SHAPE_MODEL_V1.md` defines the feature set that feeds this research.  
V2 research drives which Race Shape features are worth computing.  
The two documents are paired: Race Shape defines features, Midprice V2 defines the evaluation protocol.

---

## Hard Constraints (permanent)

```
No scoring changes — VP is unchanged
No routing changes — candidate_route() is unchanged
No staking changes — execution_allowed=False always
No model promotion — Gate V3 not yet defined
All V2 work is shadow/research/paper only
Learning consume requires Council PASS_TO_LEARNING + operator approval
```
