# VÉLØ Candidate Lane Shadow Ledger Design V1

**Created:** 2026-04-29 00:43 UTC
**Status:** DESIGN ONLY — no live rows exist yet

---

## Purpose

This document specifies the per-lane append ledger schema for all 6 VÉLØ candidate lanes.
Each lane accumulates shadow evidence rows from closed race results.
No staking. No routing changes. Evidence accumulation and operator visibility only.

---

## Lane Summary

| # | Lane | Status | SR (baseline) | Frame | n | Priority |
|---|---|---|---|---|---|---|
| 2 | 🔵 VP≥0.30 + Tier A | SHADOW_CANDIDATE | 40.1% | 77.2% | 162 | 2 |
| 1 | 🔵 Market Deception Score > 0.50 | SHADOW_CANDIDATE | 54.8% | 96.8% | 31 | 1 |
| 3 | 🔵 Improvement Score > 0.40 | SHADOW_CANDIDATE | 43.5% | 82.3% | 62 | 3 |
| 4 | 🟡 Place Probability > 0.80 | WATCHLIST | 31.6% | 66.8% | 392 | 4 |
| 5 | 🔴 Tier B + VP < 0.30 (SUPPRESS CANDIDATE) | SUPPRESS_CANDIDATE | 16.9% | 44.1% | 272 | 5 |
| 6 | 🔬 Mid-Price Winner Forensics (SP 3.0–8.5 Miss Zone) | FORENSICS_ONLY | — | 352 misses | 352 | 6 |

---

## Row Schema

Every qualifying row appended to any lane ledger contains these fields:

| Field | Type | Note |
|---|---|---|
| `row_id` | uuid | auto-generated |
| `lane_id` | text | VP30_TIER_A | MARKET_DECEPTION_HIGH | etc |
| `date` | date | race date YYYY-MM-DD |
| `race_id` | text | from sigma_audits.race_id |
| `race_time` | text | off_time HH:MM |
| `course` | text | track/course name |
| `horse` | text | predicted pick name |
| `velo_prime_prob` | float | VP score 0-1 |
| `decision_tier` | text | A/B/C/D/X |
| `lane_condition` | text | human-readable condition that qualified this row |
| `signal_value` | float | the key signal value that triggered the lane (MDS, improve_score, VP, etc) |
| `market_deception_score` | float | null if not relevant |
| `improvement_score` | float | null if not relevant |
| `place_prob` | float | null if not relevant |
| `sp_decimal` | float | starting price decimal at race time |
| `result_position` | int | 1=winner, 2=placed, null=unranked |
| `won` | boolean | true if outcome=WIN |
| `framed` | boolean | true if outcome=WIN or PLACED |
| `missed_winner` | boolean | true if outcome=MISS |
| `missed_winner_sp` | float | SP of actual winner if missed |
| `miss_class` | text | mid_priced_won | outsider_won | short_fav_won | market_decoy_followed | null |
| `router_source` | text | V1_BASE | V2_CLASS4_ONLY | V6_GOLD_SEAM | NONE |
| `sidecar_sources` | text[] | list of sidecars that also fired: MDS_HIGH | IMPROVE_HIGH | PLACE_HIGH |
| `race_archetype` | text | Structure | Compression | Null |
| `audit_status` | text | COMPLETE | PENDING | UNRESOLVABLE |
| `created_at` | timestamptz | UTC timestamp of row creation |
| `sigma_audit_id` | uuid | FK to sigma_audits.id |
| `verdict_id` | uuid | FK to velo_verdicts.id if available |

**Primary key:** `lane_id + race_id`
**Append-only:** True
**Dedup rule:** If race_id already exists for a lane_id, skip — do not overwrite.

---

## Lane Specifications

### 🔵 VP≥0.30 + Tier A

**Lane ID:** `VP30_TIER_A`
**Status:** SHADOW_CANDIDATE
**Classification:** PROVEN_SIGNAL_SHADOW_TRACK
**Priority:** 2

**Condition:** `velo_prime_prob >= 0.30 AND decision_tier == 'A'`

*Races where velo_prime_prob >= 0.30 AND decision_tier == 'A'. The primary live signal gate.*

**Baseline Evidence (49-day unified audit):**

| n | SR | Frame | Source |
|---|---|---|---|
| 162 | 40.1% | 77.2% | velo_unified_evidence_audit_v1 (49 days) |

**Promotion Gates:**

| Gate | Requirement |
|---|---|
| Minimum n | 250 |
| SR floor | 35% |
| Frame floor | 70% |
| Multi-week required | True |
| Human review required | True |
| Next stage | WATCHLIST |

*n=250 gives statistical stability. SR floor is set below current 40.1% to allow for natural variance.*

**Freeze Rules:**

- Auto-freeze: `SR < 0.20 at n >= 50 OR frame_rate < 0.55 at n >= 50`
- Review-freeze: `consecutive_weak_days >= 10`
- Unfreeze: operator review + SR recovery above floor

**Ledger file:** `data/shadow_ledgers/vp30_tier_a_shadow_ledger.csv`

---

### 🔵 Market Deception Score > 0.50

**Lane ID:** `MARKET_DECEPTION_HIGH`
**Status:** SHADOW_CANDIDATE
**Classification:** ELITE_SIGNAL_SHADOW_TRACK
**Priority:** 1

**Condition:** `market_deception_score > 0.50`

*Races where market_deception_score > 0.50. POLARITY FLIP CONFIRMED: previously used as a decoy blocker. 49-day audit shows SR=54.8%, Frame=96.8% — this signal identifies live contenders the market shape is disguising. Highest upside signal in the system.*

**Baseline Evidence (49-day unified audit):**

| n | SR | Frame | Source |
|---|---|---|---|
| 31 | 54.8% | 96.8% | velo_unified_evidence_audit_v1 (49 days) |

> **Warning:** n=31 — elite signal but small sample. Treat with discipline.

**Promotion Gates:**

| Gate | Requirement |
|---|---|
| Minimum n | 75 |
| SR floor | 40% |
| Frame floor | 80% |
| Multi-week required | True |
| Human review required | True |
| Next stage | WATCHLIST |

*Lower n gate (75 vs 250) because the signal is extreme. If SR holds above 40% at n=75 this warrants urgent human review. Extra caution: if SR drops below 30% at n=50, freeze immediately — extreme signals that regress can indicate overfitting.*

**Freeze Rules:**

- Auto-freeze: `SR < 0.25 at n >= 40 OR frame_rate < 0.65 at n >= 40`
- Review-freeze: `consecutive_weak_days >= 7`
- Unfreeze: operator review — do not auto-unfreeze this lane

> **Polarity Watch:** If SR falls below global baseline (20.6%), the polarity flip hypothesis fails — escalate immediately.

**Ledger file:** `data/shadow_ledgers/market_deception_high_shadow_ledger.csv`

---

### 🔵 Improvement Score > 0.40

**Lane ID:** `IMPROVEMENT_SCORE_HIGH`
**Status:** SHADOW_CANDIDATE
**Classification:** PROVEN_SIGNAL_SHADOW_TRACK
**Priority:** 3

**Condition:** `improvement_score > 0.40`

*Races where improvement_score > 0.40. Captures horses showing progressive form improvement.*

**Baseline Evidence (49-day unified audit):**

| n | SR | Frame | Source |
|---|---|---|---|
| 62 | 43.5% | 82.3% | velo_unified_evidence_audit_v1 (49 days) |

**Promotion Gates:**

| Gate | Requirement |
|---|---|
| Minimum n | 100 |
| SR floor | 35% |
| Frame floor | 75% |
| Multi-week required | True |
| Human review required | True |
| Next stage | WATCHLIST |

*n=62 at baseline. Need 100 to confirm. SR floor set below current 43.5% to allow variance.*

**Freeze Rules:**

- Auto-freeze: `SR < 0.22 at n >= 60 OR frame_rate < 0.60 at n >= 60`
- Review-freeze: `consecutive_weak_days >= 10`
- Unfreeze: operator review + SR recovery above floor

**Ledger file:** `data/shadow_ledgers/improvement_score_high_shadow_ledger.csv`

---

### 🟡 Place Probability > 0.80

**Lane ID:** `PLACE_PROB_HIGH`
**Status:** WATCHLIST
**Classification:** PROMISING_SIGNAL_WATCHLIST
**Priority:** 4

**Condition:** `place_prob > 0.80`

*Races where place_prob > 0.80. Large sample signal (n=392). SR=31.6% is meaningful but requires VP or Tier A overlay before candidate promotion. Currently WATCHLIST — not yet a shadow candidate.*

**Baseline Evidence (49-day unified audit):**

| n | SR | Frame | Source |
|---|---|---|---|
| 392 | 31.6% | 66.8% | velo_unified_evidence_audit_v1 (49 days) |

**Promotion Gates:**

| Gate | Requirement |
|---|---|
| Minimum n | 500 |
| SR floor | 28% |
| Frame floor | 65% |
| Multi-week required | N/A |
| Human review required | True |
| Next stage | SHADOW_CANDIDATE (with VP/Tier overlay requirement) |

*Place probability alone is not enough — it is measuring a different dimension than VP. Only valid as a shadow candidate when combined with VP≥0.30 or Tier A. Track volume at n=392 is the highest in the system — watch for sample dilution.*

**Freeze Rules:**

- Auto-freeze: `SR < 0.18 at n >= 200 OR frame_rate < 0.50 at n >= 200`
- Review-freeze: `consecutive_weak_days >= 14`
- Unfreeze: operator review

**Ledger file:** `data/shadow_ledgers/place_prob_high_shadow_ledger.csv`

---

### 🔴 Tier B + VP < 0.30 (SUPPRESS CANDIDATE)

**Lane ID:** `B_TIER_LOW_VP_SUPPRESS`
**Status:** SUPPRESS_CANDIDATE
**Classification:** SUPPRESS_CANDIDATE
**Priority:** 5

**Condition:** `decision_tier == 'B' AND velo_prime_prob < 0.30`

*Races where decision_tier == 'B' AND velo_prime_prob < 0.30. SR=16.9%, Frame=44.1% — confirmed drag on global metrics. Suppression test: removing these 272 races improves global SR from 20.6% → 21.6% at a coverage cost of -21.8%. Tracking to confirm drag persists before suppression protocol.*

**Baseline Evidence (49-day unified audit):**

| n | SR | Frame | Source |
|---|---|---|---|
| 272 | 16.9% | 44.1% | velo_unified_evidence_audit_v1 (49 days) |

**Suppression Review Gates:**

- Minimum n: 350
- SR ceiling: 18% (suppress if SR stays below this)
- Frame ceiling: 50%

*If SR remains below 18% and frame below 50% at n=350, suppression protocol is warranted. Present evidence to operator for decision. Do NOT auto-suppress — this is a coverage reduction and requires explicit approval.*

**Ledger file:** `data/shadow_ledgers/b_tier_low_vp_suppress_ledger.csv`

---

### 🔬 Mid-Price Winner Forensics (SP 3.0–8.5 Miss Zone)

**Lane ID:** `MID_PRICE_WINNER_FORENSICS`
**Status:** FORENSICS_ONLY
**Classification:** FORENSICS_ONLY
**Priority:** 6

**Condition:** `outcome == 'MISS' AND actual_winner_sp >= 3.0 AND actual_winner_sp <= 8.5`

*Races where VÉLØ missed and the actual winner had SP between 3.0 and 8.5. 352 misses = 58% of all misses across 49 days. This is the primary unsolved problem. No scoring function. No execution target. Research only.*

**Baseline Evidence:**
- Miss count: 352 (58% of all misses)
- SP zone: 3.0 to 8.5

**Research Questions:**

- 1. SP clustering — where within 3.0–8.5 do misses concentrate? (3.0–4.5 vs 5.0–8.5?)
- 2. VP distribution — what VP score did VÉLØ assign to these races when it missed?
- 3. Tier distribution — are mid-price winner misses concentrated in Tier B/C?
- 4. Race type distribution — flat vs jump? Class 3/4/5 split?
- 5. Course/distance pattern — do certain tracks produce more mid-price winner misses?
- 6. Time of meeting — do mid-price winner misses cluster in later races?

**Goal:** Determine whether VÉLØ is systematically underweighting mid-price contenders, or whether this is irreducible noise at 3.0–8.5 SP. If systematic, identify which feature or model component is responsible.

**Ledger file:** `data/shadow_ledgers/mid_price_winner_forensics_ledger.csv`

---

## Governance

### Principles

- All ledgers are append-only. No row is ever deleted or modified after writing.
- A race qualifies for a lane when it meets the lane condition at the time of prediction.
- Lane qualification is determined from sigma_audit rows (post-result), not from racecard.
- Signal values (MDS, improve_score, VP) come from velo_verdicts or verdict JSON — not recalculated.
- Ledger rows are written by the shadow ledger append script after each sigma batch.
- No staking or betting decision is ever derived from ledger state.
- No lane can be promoted without explicit operator approval.

### Lifecycle

- DESIGN (current) — lane defined, schema specified, no live rows
- SHADOW_CANDIDATE — live rows accumulating, no execution
- WATCHLIST — n gate passed, SR/Frame reviewed, watching for stability
- PAPER_EXECUTION — operator tracks as if executing, still no staking
- LIVE_DISCUSSION — sustained evidence, operator review for live activation
- LIVE_ACTIVATION — explicit operator approval, full audit trail required

**Current stage (all lanes):** DESIGN

### Append Script

- **Script:** `scripts/run_candidate_lane_shadow_append.py`
- **Status:** NOT_YET_BUILT
- **Purpose:** Reads today's sigma results, evaluates each lane condition, appends qualifying rows to ledger CSVs.
- **Next mission:** `candidate_lane_shadow_ledger_dry_run`

### Hard Rules

- NO staking or betting based on ledger state.
- NO router rule changes from ledger observations.
- NO model training based on ledger patterns.
- NO promotion without operator approval.
- NO auto-unfreeze of MARKET_DECEPTION_HIGH — operator-only.

---
*VÉLØ Candidate Lane Shadow Ledger Design V1 | 2026-04-29 00:43 UTC*