# NAMED LANE OUTCOME TRACKING V1

**Classification:** ADVISORY_TRACKING_ONLY | NO_SCORING_CHANGE | LOOP_CLOSURE_ACTIVE
**Built:** 2026-05-17
**Depends on:** NAMED_SIGNAL_LANE_OPERATIONALIZATION_V1 (lanes defined), SIGMA_2K_SAFE_TRAINING_SLICE_V1 (evidence corpus)

---

## Purpose

Named Lane Operationalization V1 created the classification layer.
Named Lane Outcome Tracking V1 closes the feedback loop:

```
Before:
  candidate → lane label → advisory action

Now:
  candidate → lane label → result → SR/frame/ROI → gate status → promotion decision
```

Every lane has a measurable survival record. Every day that record updates.
This document defines the protocol.

---

## Lane Lifecycle

```
1. PRE-RACE
   run_prime_today.py scores today's races
   build_named_lane_operator_card.py classifies each top pick into a named lane
   Action labels: PRIORITY_WATCH | WATCH | SUPPRESS_ADVISORY | HOLD_MORE_DATA

2. POST-RACE
   run_results_sigma.py downloads results and closes sigma loops
   named_lane_outcome_tracker.py reads the training corpus (result_matched=True rows)
   Per-lane cumulative stats: n, wins, frames, SR, frame_rate, ROI, LLR

3. WEEKLY
   named_lane_promotion_gate_report.py applies 7-gate promotion gate logic
   Verdict per lane: INSUFFICIENT_N | EARLY_REVIEW_READY | GATE_BLOCKED | SHADOW_POLICY_CANDIDATE
   Operator reads gate report. No automatic promotion. Operator decision only.

4. MILESTONE
   When any lane crosses its promotion gate threshold → operator council discussion
   Evidence must sustain across at least one full weekly review before any policy change
   No lane change affects scoring, routing, staking, or Telegram without explicit approval
```

---

## Input Artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Training corpus | `data/training/sigma_2k_training_dataset_latest.parquet` | Historical outcomes (result_matched=True) |
| Operator card | `data/reports/named_lane_operator_card_latest.json` | Today's classified candidates |
| Outcome tracker snapshot | `data/reports/named_lane_outcome_tracker_latest.json` | Previous run baseline for delta |

---

## Output Artifacts

| Artifact | Path | Overwrite cadence |
|---|---|---|
| Outcome tracker JSON | `data/reports/named_lane_outcome_tracker_latest.json` | Every run |
| Outcome tracker MD | `data/reports/named_lane_outcome_tracker_latest.md` | Every run |
| Outcome tracker snapshot | `data/reports/named_lane_outcome_tracker_YYYY_MM_DD.json` | Dated, immutable |
| Gate report JSON | `data/reports/named_lane_promotion_gate_report_latest.json` | Every run |
| Gate report MD | `data/reports/named_lane_promotion_gate_report_latest.md` | Every run |

---

## Per-Lane Metrics Tracked

| Metric | Definition |
|---|---|
| n | Total candidates with results (result_matched=True) |
| wins | Horses that won |
| frames | Horses that placed |
| misses | Candidates that did not win |
| SR | Strike rate = wins / n × 100 |
| frame_rate | Frame rate = frames / n × 100 |
| ROI | Flat £1 stake ROI = (sum of winning SPs − n) / n × 100 |
| avg_SP | Average starting price across all n |
| median_SP | Median starting price |
| biggest_winner | Horse with highest SP that won (name, SP, VP, date) |
| worst_false_positive | Highest-VP horse that did not win (name, VP, SP, date) |
| LLR | Longest losing run by date order |
| daily_delta | Change in n and SR since previous snapshot |
| promotion_gate | Current gate status and distance to next threshold |
| collapse_check | SR vs 2026-05-17 reference — STABLE / COLLAPSE_WARNING / INSUFFICIENT_N |

---

## Promotion Gate Definitions

All 7 gates must pass for a SHADOW_POLICY_CANDIDATE verdict.
No gate passes automatically change any live setting.

| Gate | Condition | Rationale |
|---|---|---|
| Gate 1 | n ≥ 50 | Minimum viable evidence — below this is noise |
| Gate 2 | n ≥ 100 | Serious policy review threshold |
| Gate 3 | SR ≥ 35% (15pp above 20% random baseline) | Material lift confirmed |
| Gate 4 | Frame rate ≥ 70% | Frame coverage healthy — model finding right race zones |
| Gate 5 | ROI ≥ 0% | Not losing money on flat stake — SR is real, not SP illusion |
| Gate 6 | LLR ≤ 25% of n | Losing-run risk tolerable — no catastrophic streaks |
| Gate 7 | No subgroup collapse | No class or course group shows SR > 20pp below lane SR at n≥10 |

### Gate Verdicts

| Verdict | Meaning |
|---|---|
| INSUFFICIENT_N | n < 50 — not enough evidence to assess |
| EARLY_REVIEW_READY | Gates 1, 3-7 pass, n ≥ 50 but < 100 — early discussion only |
| GATE_BLOCKED | n ≥ 50 but at least one gate fails |
| SHADOW_POLICY_CANDIDATE | All 7 gates pass AND n ≥ 100 — operator promotion discussion required |

---

## Collapse Gates

Signal collapse triggers a council review. Defined as SR dropping >5pp from the 2026-05-17 reference
at same or larger n.

| Lane | Reference SR | Reference n | Collapse Threshold |
|---|---|---|---|
| MDS_HIGH_LANE | 69.2% | 39 | SR < 64% at n ≥ 50 |
| IMPROVER_LANE | 42.1% | 38 | SR < 37% at n ≥ 50 |
| VP40_LANE | 45.3% | 150 | SR < 40% at n ≥ 200 |
| SHORTFAV_VP30 | 52.2% | 186 | SR < 47% at n ≥ 200 |
| MIDPRICE_SUPPRESS | 16.0% | 545 | Track upward drift above 22% |
| LONGSHOT_SUPPRESS | 6.3% | 413 | Track upward drift above 12% |

---

## Weekly Cadence

Run after each sigma close, or at minimum every Sunday:

```bash
# 1. Rebuild training corpus
source venv/bin/activate
PYTHONPATH=. python scripts/build_sigma_training_dataset.py

# 2. Named lane stats (corpus-level)
PYTHONPATH=. python scripts/build_named_signal_lanes.py --date YYYY-MM-DD

# 3. Operator card (today's candidates)
PYTHONPATH=. python scripts/build_named_lane_operator_card.py --date YYYY-MM-DD

# 4. Outcome tracker (closes the loop)
PYTHONPATH=. python scripts/named_lane_outcome_tracker.py --date YYYY-MM-DD

# 5. Promotion gate report (7-gate analysis)
PYTHONPATH=. python scripts/named_lane_promotion_gate_report.py --date YYYY-MM-DD

# 6. Weekly lane tracker (delta vs last snapshot)
PYTHONPATH=. python scripts/run_weekly_signal_lane_tracker.py --date YYYY-MM-DD

# 7. Mission Control (reads all of the above)
PYTHONPATH=. python scripts/velo_mission_control.py --date YYYY-MM-DD
```

Read in Mission Control:
- NAMED SIGNAL LANES V2 CARD: today's classified candidates
- LANE OUTCOME CLOSURE: cumulative SR/ROI/gate status per lane
- NEXT REVIEW THRESHOLDS: days until each promotion gate

---

## Forbidden Actions

```
❌ No automatic promotion based on gate verdict alone
❌ No scoring change triggered by lane outcome
❌ No staking change triggered by lane SR
❌ No router rule change based on lane performance
❌ No model weight change based on lane outcome tracking
❌ No Playbook G promotion based on lane gate report
❌ No Telegram format change
❌ No live state mutation
❌ No promotion discussion before n ≥ 100 and all 7 gates pass
```

---

## No-Scoring-Change Rule

This system is read-only relative to the live scoring path.

The outcome tracker reads:
- Training corpus parquet (result_matched=True rows)
- Named lane operator card JSON

It writes:
- Reports directory only
- No modification to any model, ensemble weight, router mask, or live verdict

The promotion gate report reads:
- Outcome tracker JSON
- Training corpus parquet (for subgroup analysis)

It writes:
- Reports directory only
- No modification to any live system component

---

## Governance

```
NO_SCORING_CHANGE
NO_MODEL_CHANGE
NO_ROUTER_CHANGE
NO_STAKING_CHANGE
NO_TELEGRAM_CHANGE
NO_PLAYBOOK_G_PROMOTION
NO_LIVE_STATE_MUTATION
ADVISORY_TRACKING_ONLY
```

---

## VP40_LANE — First SHADOW_POLICY_CANDIDATE (2026-05-17)

As of the first run, VP40_LANE has passed all 7 gates:

```
n=150  SR=45.3%  frame=80.7%  ROI=+8.2%  LLR acceptable  No subgroup collapse
Verdict: SHADOW_POLICY_CANDIDATE
```

This is advisory. No change is made. The operator must review and decide.
Gate passage does not trigger any live modification.
A shadow policy discussion means: what would a VP40 filter look like as an actual policy?
The discussion is not the policy. The policy requires separate evidence and approval.

---

*NAMED_LANE_OUTCOME_TRACKING_V1 — 2026-05-17*
*Depends on: NAMED_SIGNAL_LANE_OPERATIONALIZATION_V1*
*Evidence base: SIGMA_2K_SAFE_TRAINING_SLICE_V1 at 1310 rows*
*Next review: after any lane crosses promotion gate or collapse threshold*
