# VFU-10 — Time-Safe Passport Override Validation
**Version:** VFU_10_TIME_SAFE_PASSPORT_OVERRIDE_V1  
**Timestamp:** 2026-06-14T23:03:09.435993+00:00  
**ERA_START boundary:** 2026-05-08  
**VP Threshold:** 0.4 (UNCHANGED)  

---

## Executive Summary

This investigation answers the operator's red-line audit question:
> *Did the Passport evidence exist before each VFU race? Or did the Passport include the winning run itself?*

Findings:
- **Kakirra**: `TEMPORAL_CONTAMINATION_UNRESOLVABLE` — not in training data. All Passport signals are post-era.
- **Man is King**: `PARTIAL_CONTAMINATION` — win_rate is contaminated, but SP shortening IS time-safe (avg_sp 251→12.6 over 36 pre-era runs).
- **Time-safe SP shortening** shows directional separation between VP<0.40 winners and non-winners.
- **Time-safe win_rate** does NOT separate the groups cleanly.
- **Passport Override remains DRY_RUN_ONLY.** No doctrine promotion.
- **VP threshold unchanged at 0.40.**

---

## Group Statistics (Time-Safe Only)

| Metric | Group A (VP<0.40 Win) | Group B (VP≥0.40 Win) | Group C (VP<0.40 Non-Win) |
|--------|----------------------|----------------------|--------------------------|
| Distinct horses | 97 | 54 | 314 |
| Pre-era coverage | 58 (59.8%) | 13 (24.1%) | 205 (65.3%) |
| Avg pp_win_rate (pre-era) | 0.134 | 0.113 | 0.111 |
| Avg pp_avg_sp_last5 | 16.4 | 20.3 | 25.0 |
| % SP shortened (<20.0) | 67.2% | 69.2% | 59.5% |
| % win_rate meaningful (>0.15) | 27.6% | 30.8% | 21.9% |
| % course experienced | 43.1% | 38.5% | 47.3% |
| % class dropper | 15.5% | 38.5% | 17.1% |
| % has any time-safe signal | 79.3% | 92.3% | 79.0% |

---

## Temporal Contamination — Key Horses

### Kakirra (RP_UID 8866972)
**Status: `TEMPORAL_CONTAMINATION_UNRESOLVABLE`**

- Not found in `passport_features.parquet` (training data ends 2025-07-05).
- Kakirra has no pre-2026 racing history available in training data.
- Before first VFU race (2026-05-13): approximately 2 career runs, 0 wins.
- Current Passport signals are ALL derived from VFU wins:
  - `win_rate = 0.60` → comes from 3 VFU wins
  - `aw_specialist = True` → comes from Wolverhampton win (current era)
  - `position_trend = IMPROVING` → current era trajectory
  - `sp_shortening` → cannot verify without pre-era SP history
- **VFU-09 forensic finding for Kakirra stands, but predictive proof is rejected.**
- Kakirra cannot be used to justify Passport Override until pre-era data is sourced.

### Man is King (RP_UID 3839266)
**Status: `PARTIAL_CONTAMINATION`**

- Found in `passport_features.parquet`: 36 career runs to 2025-07-03.
- **Time-safe pre-era snapshot:**
  - `pp_win_rate = 0.0` (0/36 wins) — NOT predictive
  - `pp_career_runs = 36`
  - `pp_avg_sp_last5 = 12.6` — SP has SHORTENED over career (from ~251 first runs)
- Current Passport `win_rate = 0.40` is contaminated by 2 current-era VFU wins.
- **SP shortening IS a valid time-safe signal**: the market was already backing him
  by end of training data (avg_sp 12.6 at last pre-era run).
- **Win_rate was 0.0 before current era** — VFU-09's use of win_rate as discriminating
  signal for Man is King is contaminated and must be discounted.

---

## Required Questions

**Q1_how_many_vp_low_winners_tested:**
97 distinct horses (102 runs)

**Q2_how_many_had_pre_era_coverage:**
58/97 (59.8%)

**Q3_how_many_temporally_unresolved:**
39 horses — 39 from Group A

**Q4_did_time_safe_features_separate_groups:**
PARTIAL — SP shortening shows directional separation (A vs C), but win_rate does NOT separate cleanly (both groups have low pre-era win rates). Group A: 67% SP shortened vs Group C: 60%. Win_rate: Group A avg=0.134 vs Group C avg=0.111.

**Q5_which_features_separated_best:**
pp_avg_sp_last5 (SP shortening) shows strongest directional separation. pp_win_rate shows weak or no pre-era separation. pp_class_moved_down (class drop) directional but small n.

**Q6_was_kakirra_predictive_or_contaminated:**
CONTAMINATED. Kakirra not in training data (no pre-2026 history). All VFU-09 Passport signals for Kakirra derive from post-era wins. Cannot be used as predictive proof. Status: TEMPORAL_CONTAMINATION_UNRESOLVABLE.

**Q7_was_man_is_king_predictive_or_contaminated:**
PARTIALLY_CONTAMINATED. Pre-era win_rate=0.0 (0/36 runs) — not predictive. BUT SP shortening IS time-safe: avg_sp fell 251→12.6 over 36 pre-era runs. SP shortening signal was visible before the VFU era. Status: PARTIAL_CONTAMINATION.

**Q8_is_passport_override_still_viable:**
VIABLE_BUT_UNPROVEN. SP shortening shows directional pre-era signal. Win_rate does not. Identity + SP shortening together may be a valid pre-race signal, but n is too small for doctrine promotion. Requires more evidence.

**Q9_is_it_ready_for_live_use:**
NO. Watchlist remains DRY_RUN_ONLY. Contamination audit incomplete for 39/97 Group A horses. Time-safe sample too small. Operator must review before any live use.

**Q10_should_vp_threshold_change:**
NO. VP threshold remains 0.40 unchanged. Time-safe analysis does not yet prove individual-horse overriding of VP. VP remains valid as population signal.

**Q11_should_passport_override_remain_dry_run:**
YES. Passport Override remains DRY_RUN_ONLY. Temporal contamination reduces confidence in VFU-09 findings. VFU-10 time-safe comparison is directional but inconclusive.

**Q12_what_should_vfu_11_focus_on:**
VFU-11 should focus on expanding time-safe snapshot coverage (42 Group A horses have no training data). Options: (1) Racing Post historical data ingestion for new-era horses like Kakirra; (2) In-era Passport snapshot build: capture Passport state AT each race date using per-race runs before that date; (3) Identify if SP shortening threshold (pp_avg_sp_last5 < 20) alone is sufficient as a standalone Passport Override qualifier.

---

## Passport Override Watchlist (Dry-Run Only)

**Candidates with time-safe pre-era signal:** 46
**Status: DRY_RUN_ONLY — do_not_merge=True on all entries**

| Horse | pp_win_rate (pre-era) | pp_avg_sp_last5 (pre-era) | SP Shortened | Signals |
|-------|----------------------|--------------------------|--------------|---------|
| Glamazon | 0.000 | 11.0 | YES | sp_shortened, course_experienced |
| Lough Leane | 0.273 | 8.7 | YES | sp_shortened, win_rate_meaningful |
| Lambourn | 0.667 | 6.0 | YES | sp_shortened, win_rate_meaningful, course_experienced |
| Lake Forest | 0.300 | 11.4 | YES | sp_shortened, win_rate_meaningful, course_experienced |
| Sweet Reward | 0.149 | 12.6 | YES | sp_shortened, course_experienced |
| Assaranca | 0.000 | 4.0 | YES | sp_shortened |
| Harry Brown | 0.121 | 8.6 | YES | sp_shortened, course_experienced |
| Man Is King | 0.000 | 12.6 | YES | sp_shortened, or_falling |
| See The Fire | 0.250 | 16.1 | YES | sp_shortened, win_rate_meaningful, course_experienced |
| Rahiebb | 0.250 | 5.1 | YES | sp_shortened, win_rate_meaningful |
| Believeinmenow | 0.000 | 6.4 | YES | sp_shortened, class_dropper |
| Scandinavia | 0.250 | 2.5 | YES | sp_shortened, win_rate_meaningful |
| Bizarre Law | 0.103 | 17.1 | YES | sp_shortened, course_experienced |
| Notable Speech | 0.556 | 3.7 | YES | sp_shortened, win_rate_meaningful, course_experienced |
| Lethimfly | 0.111 | 37.2 | no | course_experienced |
| Genbu | 0.000 | 17.0 | YES | sp_shortened, or_falling |
| Beaujolais Nouveau | 0.125 | 5.1 | YES | sp_shortened |
| No Gain | 0.000 | 17.2 | YES | sp_shortened |
| Filey Beach | 0.000 | 20.9 | no | course_experienced |
| Alpine Sierra | 0.087 | 7.5 | YES | sp_shortened, course_experienced, or_falling |
| ... | | | | (26 more) |

---

## Uncovered Cases (No Pre-Era Snapshot)

**Total:** 189 horses (across all groups)
**Group A uncovered:** 39

These horses cannot have their pre-era Passport signals verified.
No Passport Override conclusions can be drawn for uncovered horses.

---

## Hard Rules — Confirmed

- VP_THRESHOLD: 0.40 — UNCHANGED
- canonical Passport: NOT MUTATED
- Supabase: NOT WRITTEN
- live scoring: NOT CHANGED
- model: NOT PROMOTED
- Telegram: NOT SENT
- Racing API: NOT RESTORED
- Mar–Apr: NOT EXTRACTED
- Passport Override: DRY_RUN_ONLY

---

## Final Classifications

```
VFU_10_TIME_SAFE_PASSPORT_OVERRIDE_VALIDATION_COMPLETE
TEMPORAL_CONTAMINATION_AUDITED
KAKIRRA_PREDICTIVE_PROOF_REJECTED_FOR_NOW
MAN_IS_KING_PARTIAL_TIME_SAFE_SIGNAL_REVIEWED
TIME_SAFE_PASSPORT_FEATURES_TESTED
PASSPORT_OVERRIDE_REMAINS_DRY_RUN_ONLY
NO_VP_THRESHOLD_CHANGE
NO_LIVE_DOCTRINE_PROMOTION
CANONICAL_HORSE_PASSPORT_NOT_MUTATED
NO_MAR_APR_EXTRACTION
NO_LIVE_SCORING_CHANGE
NO_SUPABASE_WRITES
NO_MODEL_PROMOTION
NO_TELEGRAM_SEND
NO_RACING_API_RESTORATION
```