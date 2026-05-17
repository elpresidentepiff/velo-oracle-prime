# VELO WEEKLY SIGNAL LANE TRACKING V1

**Classification:** ADVISORY_TRACKING_ONLY | NO_SCORING_CHANGE | GROWTH_CADENCE_DEFINED
**Owner:** Operator
**Started:** 2026-05-17
**Purpose:** Weekly cadence for tracking named signal lanes until 2K clean training-safe rows

---

## Why This Document Exists

The SIGMA_2K_SAFE_TRAINING_SLICE_V1 closed at 1310 training-safe rows on 2026-05-17.
Category A recovery from Supabase velo_verdicts was exhausted (SUPABASE_VERDICT_RECOVERY_CLOSURE_2026-05-17.md).

Growth to 2K is through daily clean accumulation only. This document defines the weekly
cadence for monitoring that growth and the named signal lanes that are tracking toward
shadow policy promotion.

---

## 2K Milestone Definition

```
Current (2026-05-17):   1310 training-safe rows
Target:                 2000 training-safe rows
Gap:                    690 rows
Estimated arrival:      ~2026-06-07 to 2026-06-14 (30–50 clean rows/day)
```

A row is training-safe when:
1. result_matched = True (local results file confirms outcome)
2. NOT Category G (3+ of 4 key signal fields not missing)
3. NOT Category F (horse_id resolved)
4. NOT X-tier (excluded by design from SR/frame calculations)

---

## Named Signal Lanes — Active Tracking

| Lane | Definition | n | SR | Status |
|---|---|---|---|---|
| MDS_HIGH_LANE ⚠️ | VP>=0.30 AND MDS>0.50 | 39 | 69.2% | PROVEN (⚠️ n<50) |
| IMPROVER_LANE ⚠️ | VP>=0.30 AND improvement>0.40 | 38 | 42.1% | PROVEN (⚠️ n<50) |
| VP40_LANE | VP>=0.40 | 150 | 45.3% | PROVEN |
| VP40_TIER_A_LANE | VP>=0.40 AND tier A | 132 | 44.7% | PROVEN |
| SHORTFAV_VP30 | SP<3.0 AND VP>=0.30 | 186 | 52.2% | PROVEN |
| MIDPRICE_ROUTER_QUAL ⚠️ | SP 3.0–8.5 AND router V1/V2/V6 | 18 | 33.3% | INSUFFICIENT_SAMPLE |
| MIDPRICE_SUPPRESS | SP 3.0–8.5 AND no router | 545 | 16.0% | SUPPRESS_CONFIRMED |
| LONGSHOT_SUPPRESS | SP>8.5 | 413 | 6.3% | SUPPRESS_CONFIRMED |

*Baseline from 2026-05-17 1310-row corpus (build_named_signal_lanes.py run). Re-run weekly.*

---

## Weekly Cadence — What To Check

Run every Sunday (or after 100+ new rows accumulated):

```bash
# 1. Rebuild training dataset from current corpus
source venv/bin/activate
PYTHONPATH=. python scripts/build_sigma_training_dataset.py

# 2. Rebuild named lane tracking
PYTHONPATH=. python scripts/build_named_signal_lanes.py --date YYYY-MM-DD

# 3. Rebuild regime audit
PYTHONPATH=. python scripts/sigma_2k_regime_audit.py

# 4. Rebuild ablation audit
PYTHONPATH=. python scripts/sigma_2k_feature_ablation_audit.py
```

Then review:
- `data/reports/named_signal_lanes_latest.md` — lane stats + today's candidates
- `data/reports/sigma_2k_regime_audit_latest.md` — full regime breakdown
- `data/reports/sigma_2k_feature_ablation_latest.md` — ablation results

---

## Weekly Evidence Packet Format

Each weekly check should record:

```
Week of: [date]
New rows since last check: [n]
Total training-safe rows: [n]
2K progress: [n/2000 = X%]

Lane movements:
  [lane]: [old_n] → [new_n]  SR=[X%] (delta=[+/-X]pp)  Status=[old → new]

Promotion reviews triggered:
  [none / list any lane where n crossed 50/100/150/200]

Signal stability check:
  MDS_HIGH SR: [X%]  (reference: 69.2% at 1310 rows)
  IMPROVER SR: [X%]  (reference: 42.1% at 1310 rows)
  VP40 SR: [X%]      (reference: 45.3% at 1310 rows)

Governance confirmation:
  No scoring change [ ]
  No model change [ ]
  No router change [ ]
  No staking change [ ]
  No Telegram change [ ]
  No Playbook G promotion [ ]
  No live state mutation [ ]
```

---

## Lane Promotion Gates

Promotions are ADVISORY ONLY. No gate automatically changes anything.

### MDS_HIGH_LANE
- SHADOW_LANE_TRACKING at n≥50 (current: ~39, ~11 rows away)
- Shadow policy discussion at n≥100 with sustained SR≥60%
- Live discussion at n≥200

### IMPROVER_LANE
- SHADOW_LANE_TRACKING at n≥100 (current: ~92, ~8 rows away)
- Shadow policy discussion at n≥150 with sustained SR≥40%
- Live discussion at n≥200

### VP40_LANE
- Already PROVEN — track for stability across 200/250/300 rows
- Model weight discussion gate: n≥300, SR sustained ≥+20pp over 20+ days

### MIDPRICE_ROUTER_QUAL
- Advisory promotion at n≥50 (current: ~18, ~32 rows away)
- Shadow policy discussion at n≥100 with SR≥35%

### MIDPRICE_SUPPRESS / LONGSHOT_SUPPRESS
- Monitor for any unexpected SR recovery
- SUPPRESS_CONFIRMED unless SR breaks above 17% at n≥100

---

## Signal Stability Reference Points

These are the 2026-05-17 reference values. Signal collapse is defined as SR dropping
>5pp below reference at same or larger n — triggers a council review.

| Signal | Reference SR | Reference n | Collapse Threshold |
|---|---|---|---|
| MDS_HIGH_LANE | 69.2% | 39 | SR<64% at n≥50 |
| IMPROVER_LANE | 42.1% | 38 | SR<37% at n≥50 |
| VP40_LANE | 45.3% | 150 | SR<40% at n≥200 |
| SHORTFAV_VP30 | 52.2% | 186 | SR<47% at n≥200 |
| MIDPRICE_SUPPRESS | 16.0% | 545 | Track upward drift >19% |
| LONGSHOT_SUPPRESS | 6.3% | 413 | Track upward drift >12% |

---

## What This Is Not

```
NOT a retraining trigger — model weights unchanged
NOT a live staking change — paper ledger only
NOT a router rule change — V1/V2/V6 lanes unchanged
NOT a scoring change — ensemble weights unchanged
NOT Playbook G promotion
NOT Telegram format change
```

Every weekly check is advisory. Evidence accumulates. Promotions are operator decisions,
not automatic triggers.

---

## Archive Protocol

Each weekly run produces:
```
data/reports/named_signal_lanes_latest.json   — overwritten each run
data/reports/named_signal_lanes_latest.md     — overwritten each run
```

For weekly archive snapshots:
```bash
cp data/reports/named_signal_lanes_latest.json \
   data/reports/named_signal_lanes_$(date +%Y_%m_%d).json
```

---

*VELO_WEEKLY_SIGNAL_LANE_TRACKING_V1 — 2026-05-17*
*Baseline: SIGMA_2K_SAFE_TRAINING_SLICE_V1 at 1310 rows*
*Recovery closure: SUPABASE_VERDICT_RECOVERY_CLOSURE_2026-05-17.md*
