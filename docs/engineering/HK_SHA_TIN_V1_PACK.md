# HK Sha Tin — Jurisdiction Pack V1

**Date:** 2026-05-23  
**Status:** DESIGN — no training, no scoring, no live deployment  
**Classification:** SHADOW/RESEARCH ONLY

---

## Pack Scope

Sha Tin is Hong Kong's all-weather championship course. It hosts all major HK prize races including the HK Cup, HK Mile, HK Vase.

| Metric | Value |
|---|---|
| Training rows | 50,976 |
| Race count | 4,080 |
| Date range | 2015-01-25 → 2025-07-05 |
| Avg field size | ~12 |
| Favourite SR | 32.1% |
| RPR correlation with win | 0.3265 |
| OR coverage | 97.1% |
| TS coverage | 0.0% |
| Win label coverage | 100.0% |
| Training verdict | TRAINING_SAFE |

---

## Source Priority (Racing API Unavailable)

| Priority | Source | URL | Auth | Status | Data |
|---|---|---|---|---|---|
| P1 | HKJC Official | `racing.hkjc.com` | None | FREE | Race cards, results, draw, class, going, odds |
| P2 | HKJC Sectionals | `racing.hkjc.com/en-us/local/information/displaysectionaltime` | None | FREE | Official 400m splits, pace maps |
| P3 | HKJC Draw Stats | `racing.hkjc.com/en-us/local/horse-racing/draw-statistics` | None | FREE | Historical draw win/place % by course+distance |
| P4 | Renavon | `renavon.com` | Subscription $99+/mo | OPTIONAL | Odds time-series, historical from 1970s |
| P5 | Apify HKJC actor | `apify.com` | API key ~$20/mo | FALLBACK | Structured scrape of HKJC |
| BLOCKED | Racing API | `api.theracingapi.com` | Was Basic Auth | UNAVAILABLE | Full racecards, horse history |

**Primary data collection path:** HKJC official site + sectionals + draw stats (all free)

---

## Canonical Course Code

| Venue | VÉLØ Code | HKJC Code | Timezone | Race Days |
|---|---|---|---|---|
| Sha Tin | `SHA` | `ST` | Asia/Hong_Kong (UTC+8) | Sat/Sun + major Wed |

**HK season:** September to July. August = no racing.

---

## Identity Rules

- **Horse identity:** HK horses have a local HKJC registration number. Use HKJC ID + horse name for matching.
- **Trainer identity:** HK operates a licensed trainer system (≈30 trainers). Names are stable.
- **Jockey identity:** Similar licensed system (≈30 jockeys). Stable names.
- **Race identity:** Generate `race_id` as `{date_YYYYMMDD}_SHA_{race_number}` (e.g. `20260315_SHA_03`).
- **Griffin detection:** A Griffin is a horse in its first HK race season. Detectable by absence of HK race history + barrier trial record.

---

## Class / Rating Mapping

HK uses its own rating system (0-140 scale, similar range to UK OR). OR coverage in parquet: 97.1%.

| HK Class | Description | Runners | Rating Band | VÉLØ class_num |
|---|---|---|---|---|
| Class 1 | Elite | 6-14 | Rating 100-140 | 1 |
| Class 2 | High | 8-14 | Rating 80-99 | 2 |
| Class 3 | Middle | 8-14 | Rating 60-79 | 3 |
| Class 4 | Lower-middle | 8-14 | Rating 40-59 | 4 |
| Class 5 | Bottom | 8-14 | Rating 0-39 | 5 |
| Griffin | Debut/unrated | 6-10 | No rating | 0 |

**Class trajectory signal:** A horse moving Class 4→3 (improvement) is NOT the same as Class 3→4 (drop). Compute `class_delta_4_runs`: sum of class movements over last 4 runs (+1 = moved up one class, -1 = moved down).

**Note from parquet (Sha Tin class distribution):**
- Class 4: 20,002 rows (39%) — most common
- Class 3: 15,393 rows (30%)
- Class 5: 6,236 rows (12%)
- Class 2: 4,888 rows (10%)
- Class 1: 759 rows (1.5%)

---

## Going Calibration

HK going is well-maintained grass. Scale: Good to Firm → Good → Good to Yielding → Yielding.
- No penetrometer equivalent published
- Going rarely extreme at Sha Tin (natural drainage, subtropical climate)
- Use going_code as-is — UK going scale applies without adjustment

---

## Draw Analysis (Critical Signal — Confirmed)

From parquet audit (50,976 Sha Tin rows):

| Draw Band | n | Win% |
|---|---|---|
| 1-3 | 12,198 | 9.9% |
| 4-6 | 12,193 | 8.7% |
| 7-9 | 11,809 | 7.0% |
| 10-12 | 10,398 | 6.9% |
| 13+ | 4,377 | 6.2% |

**Draw 1-3 wins at 60% premium over Draw 13+.** This is the strongest non-rating structural signal at Sha Tin.

Draw bias is course-configuration dependent. Sha Tin runs 1000m, 1200m, 1400m, 1600m, 1800m, 2000m, 2400m. The draw bias is most extreme on the 1200m course (tight turns) and less extreme on the 2000m (longer run to first turn). Build per-distance draw tables from HKJC draw stats page.

---

## Feature Availability

| Feature | Available | Source | Notes |
|---|---|---|---|
| RPR | YES (97.6%) | HKJC / RP data in parquet | Primary rating |
| OR (HK scale) | YES (97.1%) | HKJC racecards | Secondary rating |
| TS | NO (0.0%) | — | **DROP from HK features entirely** |
| Draw | YES | HKJC racecards | Critical signal — bias confirmed |
| Class | YES | HKJC racecards | Class 1-5 + Griffin |
| Class trajectory | COMPUTED | From race history | delta over last 4 class assignments |
| Griffin flag | YES | HKJC registry | Debut season horses |
| Barrier trial RPR | PARTIAL | HKJC trial results | For Griffins only |
| Sectional times | YES | HKJC official site (free) | 400m official splits |
| Pace rank at 400m | COMPUTED | From sectionals | Position in field at first 400m |
| Going | YES | HKJC racecards | UK scale applies |
| Distance | YES | HKJC racecards | Metres → furlongs |
| Trainer SR | COMPUTED | From `hk_horse_history` | FR-specific SR, not UK |
| Jockey SR | COMPUTED | From `hk_horse_history` | HK-specific SR, not UK |
| Market odds | YES | HKJC tote pool | Opening + late pool odds |
| Betfair | NO | No exchange in HK | Tote-only market |

---

## Benter Model Integration

The Benter model at `src/models/benter.py` is designed for HK. It combines:
- `p_fundamental`: from SQPE (RPR, class, draw, trainer/jockey)
- `p_public`: from HKJC tote odds (1 / decimal_odds)

Current calibration: α=0.9, β=1.1 (Benter 1994 paper defaults)

HK tote is different from exchange odds — the pool is large (HK is one of the world's largest betting markets by volume) and pools are efficient. β (market weight) may need to be higher in HK than in UK.

**Calibration plan:** After training `sqpe_v1_hk.pkl`, run `benter.calibrate()` on 2023-2024 holdout to find optimal α/β. Log to `models/specialist/benter_v1_hk/benter_v1_hk_calibration.json`.

---

## Flatline Gate

Define per SHA:
- `sha_flatline_alert`: if stddev of `velo_prime_prob` across all runners in a day < 0.005
- Trigger: investigate feature extraction. HK features are more stable (less form cycle variability) — threshold may be lower than UK equivalent.

---

## Learning Gate

HK shadow brain operates independently of UK Playbook G. Independent pattern library.

HK-specific patterns to watch:
- `HK_DRAW_OVERLAY` — high-RPR horse in draw 1-3 at Sha Tin — premium signal
- `HK_CLASS_DROP_DISTRESSED` — horse dropping 2 classes in 3 runs — suppression candidate
- `HK_GRIFFIN_TRIAL_SIGNAL` — Griffin with exceptional barrier trial time — positive signal
- `HK_PACE_SHAPE_PROMINENT` — sectional pace rank 1-3 at 400m — higher win rate than field

---

## Shadow Brain Target

Output: `hk_research.hk_verdicts` only  
No Telegram output  
No UK verdict table writes  
Model tags: `HK_SQPE_V1_SHADOW`, `HK_BENTER_V1_SHADOW`

---

## Promotion Gates

| Gate | Threshold | Action |
|---|---|---|
| Gate 1 | 150 top-pick decisions with outcomes | First review: SR, Brier, draw bias validation |
| Gate 2 | 300 top-pick decisions with outcomes | Full evidence review + Benter calibration check |
| Live promotion | OPERATOR DECISION ONLY | Never automatic |

---

## Legal / Source Restrictions

- HKJC official data: public, no auth required
- Renavon: commercial service — subscription required
- No Betfair in HK — HKJC tote is the only authorised betting market
- HK betting law: only HKJC-authorised channels permitted in HK. International betting operators may cover HK races.

---

## First Shadow Backtest Plan

When Phase 2 model training is approved:
1. Train `sqpe_v1_hk.pkl` on 2015-2022 Sha Tin data (n≈40K rows)
2. Validate on 2023-2024 (n≈10K rows): VP band monotonicity, Brier, draw-stratified SR
3. Calibrate Benter: run `calibrate()` on 2023-2024 holdout to find optimal α/β
4. Holdout: 2025 data (n≈5K rows) — untouched until evidence gate
5. Compare: model fav SR vs actual fav SR (32.1% baseline)
6. Validate draw bias: does model assign premium to draws 1-3 vs 13+?

---

## No Live Deployment Rule

```
HK_SQPE_V1_SHADOW outputs go to hk_research.hk_verdicts ONLY
No Telegram messages for HK racing
No betting, no staking
No UK pipeline integration
No mixing with velo_verdicts table
Operator decision required at every gate
Sha Tin and Happy Valley are separate packs with separate evidence gates
```
