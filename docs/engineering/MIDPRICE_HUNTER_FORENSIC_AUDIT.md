# VÉLØ Mid-Price Hunter — Phase 1 Forensic Audit

**Issue:** #78 — SP 3.0–8.5 Forensic Shadow Audit  
**Date:** 2026-05-20  
**Commit verified against:** `2932a12` (PR #77 merged — field-to-decision doctrine clean)  
**Dataset:** 1,576 matched verdicts, 40 race days (2026-03-17 → 2026-05-19)  
**Constraint:** No live scoring changes. No ensemble weight changes. No execution changes. Shadow/forensic only.

---

## Executive Summary

Mid-price winners (SP 3.0–8.5) account for **706 of 1,299 confirmed VÉLØ misses = 54.3%** of all misses. This is the dominant bleed zone.

The forensic analysis reveals one exceptionally clear finding:

> **MDS is the strongest available discriminant between wins and mid-price misses. When MDS ≥ 0.30, mid-price miss rate drops from 35% to 18% and SR more than doubles (24% → 55%) at VP ≥ 0.30. Only 4% of mid-price misses had MDS > 0.30 on the top pick.**

The gap is not that the system lacks signals — `market_deception_score` is LIVE_SCORING (Issue #73 confirmed). The gap is that most mid-price miss races had **weak MDS on the top pick**, and the winner's MDS was not compared pre-race (winner's per-runner sidecar scores not stored in verdict JSON — see Data Limitations section).

---

## Phase 1 — Historical Miss Extraction

### Dataset scope

| Metric | Value |
|---|---|
| Total matched verdicts | 1,576 |
| Total wins | 277 (17.6% SR) |
| Total misses | 1,299 |
| Date range | 2026-03-17 → 2026-05-19 |
| Race days | 40 |
| Courses | 81 |

### Mid-price miss extraction

| Filter | Count | % of misses |
|---|---|---|
| All misses | 1,299 | 100% |
| Winner SP 3.0–8.5 | **706** | **54.3%** |
| Winner SP < 3.0 (short fav won) | ~180 | ~14% |
| Winner SP > 8.5 (outsider won) | ~280 | ~22% |
| Unmatched/NR | ~133 | ~10% |

### Winner SP distribution within mid-price band

| SP band | Count | % of MP misses |
|---|---|---|
| 3.0–4.0 | 216 | 30.6% |
| 4.0–5.0 | 199 | 28.2% |
| 5.0–6.0 | 113 | 16.0% |
| 6.0–7.0 | 81 | 11.5% |
| 7.0–8.0 | 70 | 9.9% |
| 8.0–8.5 | 27 | 3.8% |

**The 3.0–5.0 sub-band accounts for 59% of all mid-price misses.** This is the primary target zone.

---

## Phase 2 — Top Pick Profile at Mid-Price Miss

These are the characteristics of VÉLØ's top pick *in the races it lost to a mid-price winner*.

### VP distribution at mid-price miss

| VP band | Miss count | SR in this band |
|---|---|---|
| VP < 0.20 | 235 | — (low-confidence misses) |
| VP 0.20–0.25 | 139 | — |
| VP 0.25–0.30 | 103 | — |
| VP 0.30–0.35 | 69 | — |
| VP 0.35–0.40 | 39 | — |
| VP > 0.40 | 31 | — (high-confidence misses) |

Mid-price misses at **VP ≥ 0.30: 139 cases** — these are the ones where VÉLØ had meaningful conviction and still lost to a 3.0–8.5 winner.

### Decision tier at mid-price miss

| Tier | Count | % |
|---|---|---|
| **A** | **73** | **10.3%** |
| B | 315 | 44.6% |
| C | 130 | 18.4% |
| X | 58 | 8.2% |
| D | 13 | 1.8% |
| Unmatched | 117 | 16.6% |

**73 Tier A mid-price misses** (avg VP = 0.411, avg winner SP = 4.87). These are the highest-damage cases — high conviction, wrong target. Avg winner SP of 4.87 in Tier A miss is the primary forensic target.

### Top pick signal profile at mid-price miss

| Signal (top pick) | Mean (at MP miss) | Mean (at WIN) | Discriminant ratio |
|---|---|---|---|
| `velo_prime_prob` | 0.240 | — | — (lower VP = more misses, expected) |
| `market_deception_score` | **0.064** | **0.173** | **2.7×** |
| `improvement_score` | 0.098 | 0.139 | 1.4× |
| `place_prob` | 0.600 | 0.707 | 1.2× |

**MDS is the dominant discriminant: wins have 2.7× higher MDS than mid-price misses on the top pick.**

### MDS signal breakdown

| MDS gate | Description | MP miss count | MP miss rate |
|---|---|---|---|
| MDS < 0.05 | Near-zero deception signal | 419/874 = **48%** |
| MDS 0.05–0.15 | Weak signal | — | ~45% |
| MDS 0.15–0.30 | Moderate signal | — | ~35% |
| MDS ≥ 0.30 | Strong signal | 24/114 = **21%** |

**89% of mid-price misses had top pick MDS < 0.15.**  
**Only 4% of mid-price misses had top pick MDS > 0.30.**

This means: when MDS fires, the system rarely loses to a mid-price winner. The bleed is almost entirely in low-MDS territory.

### VP + MDS combination (key shadow gate)

| Gate | n | SR | MP miss rate |
|---|---|---|---|
| VP ≥ 0.30 (all) | 443 | 31% | 31% |
| VP ≥ 0.30 + MDS < 0.30 | 345 | 24% | **35%** |
| **VP ≥ 0.30 + MDS ≥ 0.30** | **97** | **55%** | **18%** |

This is the primary finding. **Adding MDS ≥ 0.30 gate to VP ≥ 0.30: SR doubles from 24% to 55%, MP-miss halves from 35% to 18%.**

---

## Phase 3 — Profile Classification

Each mid-price miss is assigned a primary profile based on the top pick's signal state.

### Profile definitions and prevalence

| Profile | Trigger condition | Count | % of MP misses |
|---|---|---|---|
| **MIDPRICE_MARKET_DECEPTION** | Top pick MDS < 0.15 | 626 | 89% |
| **MIDPRICE_QUIET_IMPROVER** | Top pick improvement < 0.10 | 530 | 75% |
| **MIDPRICE_PLACE_VALUE** | Top pick VP 0.20–0.32 + improvement < 0.10 | 280 | 40% |
| **MIDPRICE_FAV_WEAKNESS** | Top pick is short favourite (SP < 3.0) | ~85 | ~12% |
| **MIDPRICE_COURSE_DISTANCE_FIT** | AW track | 127 | 18% of AW verdicts |
| **MIDPRICE_RP_INTENT_UNUSED** | postdata_score / is_postdata_pick / plot_conviction not available in verdict JSON | ~706 | 100% (data gap) |
| **MIDPRICE_MARK_COMPRESSION** | mark_compression data not per-winner in current store | — | requires per-runner store |
| **MIDPRICE_UNKNOWN** | None of the above | ~25 | ~4% |

**Note:** MIDPRICE_MARKET_DECEPTION and MIDPRICE_QUIET_IMPROVER are the dominant profiles and frequently co-occur. The primary profile for the top pick is MIDPRICE_MARKET_DECEPTION (low MDS = 89% of cases).

### High-damage sub-profile: Tier A mid-price miss (n=73)

| Metric | Value |
|---|---|
| Avg VP | 0.411 |
| Avg MDS | 0.184 |
| Avg improvement | 0.201 |
| Avg place_prob | 0.831 |
| Avg winner SP | 4.87 |
| Winner SP 3.0–5.0 | 49/73 = 67% |

Tier A misses have **much higher sidecar scores than the average mid-price miss** — the system correctly scored the top pick highly, but the mid-price winner was better in a dimension VÉLØ didn't detect or compare. The 10 worst Tier A mid-price misses:

| Date | Course | Top pick | VP | MDS | Improvement | Winner | Winner SP |
|---|---|---|---|---|---|---|---|
| 2026-05-09 | Warwick | Legend D'Airy | 0.659 | 0.625 | 0.366 | Nate Of Spades (IRE) | 3.50 |
| 2026-05-16 | Bangor-On-Dee | Personal Ambition | 0.622 | 0.617 | 0.538 | Grain D'Oudairies | 5.50 |
| 2026-05-02 | Thirsk | Tamam Star | 0.611 | 0.342 | 0.287 | Arapaho Gold (IRE) | 4.50 |
| 2026-04-28 | Epsom | New Zealand | 0.591 | 0.353 | 0.188 | Saxon Street (IRE) | 3.50 |
| 2026-04-23 | Beverley | Lauralynn | 0.558 | 0.185 | 0.377 | Matteo (IRE) | 3.00 |
| 2026-05-17 | Stratford | Cawthorne Cracker | 0.554 | 0.053 | 0.116 | Captain Cool | 3.00 |
| 2026-04-24 | Cork | The Publican's Son | 0.526 | 0.191 | 0.191 | Zia Zabel (IRE) | 4.33 |
| 2026-03-27 | Fontwell | Unknown Entity | 0.509 | 0.547 | 0.451 | Last Round (FR) | 6.00 |
| 2026-05-02 | Doncaster | Rocket Boots | 0.505 | 0.258 | 0.585 | Crown Of Ivy (IRE) | 3.25 |
| 2026-05-03 | Newmarket | Call Me Tomorrow | 0.498 | 0.173 | 0.116 | Zia Zabel (IRE) | 3.75 |

---

## Phase 4 — Shadow Rule Candidates

**Constraint:** All rules are shadow-only. No live scoring changes. No execution changes. Output is a `shadow_action` tag only.

### Rule 1: MIDPRICE_CHALLENGER (primary candidate)

**Trigger:** Race outcome = top pick MISS + winner SP 3.0–8.5

**Detection gate (top pick indicators):**
- VP ≥ 0.20 (race was contested)
- Top pick MDS < 0.15 (deception signal absent on top pick = displacement possible)

**Shadow action:** `MIDPRICE_CHALLENGER`

**Evidence:**
| Metric | Value |
|---|---|
| Historical catch count | 626/706 MP misses (89%) |
| False positive risk | Fires in many races where the system would win anyway |
| Estimated precision | Requires winner-side signal to sharpen |
| SR in MDS<0.15 zone | 11% (low — this zone IS the bleed zone) |
| MP miss rate when MDS<0.05 | 48% |

**Assessment:** This rule correctly identifies the bleed zone (89% recall) but has high false-positive rate without winner-side signal. The primary value is as an alert: "this race is in the displacement zone."

### Rule 2: MIDPRICE_SUPPRESS_TOP

**Trigger:** VP ≥ 0.30 + MDS < 0.30 (top pick in high-VP zone but deception signal absent)

**Shadow action:** `MIDPRICE_SUPPRESS_TOP`

**Evidence:**
| Metric | Value |
|---|---|
| n | 345 |
| SR | 24% |
| MP miss rate | 35% |
| vs MDS≥0.30 baseline | 35% miss vs 18% miss (2× bleed) |
| n in suppress zone with MP miss | 121 confirmed misses |

**Assessment:** This is the most actionable rule. When VP ≥ 0.30 but MDS < 0.30, the system is in high-confidence / low-deception-detection mode. 35% of these races will be lost to a mid-price winner. A shadow flag here prompts the operator to look for a competing deception signal.

### Rule 3: MIDPRICE_SPLIT_RACE

**Trigger:** Tier A + VP ≥ 0.40 + MDS < 0.20 + improvement < 0.20

**Shadow action:** `MIDPRICE_SPLIT_RACE`

**Evidence:**
| Metric | Value |
|---|---|
| n | 45 |
| SR | 24% |
| MP miss rate | 13% |
| Tier A + VP≥0.35 with both MDS and improvement weak | 54 cases |

**Assessment:** Smaller population but identifies the highest-stakes version of the problem: confident picks with no supporting deception or improvement signal. Low false-positive rate (13% bleed in this zone) but the MISSES here are the worst misses.

### Rule 4: MIDPRICE_NO_EDGE

**Trigger:** VP 0.20–0.30 + MDS < 0.05 + improvement < 0.10

**Shadow action:** `MIDPRICE_NO_EDGE`

**Evidence:**
| Metric | Value |
|---|---|
| n | 343 |
| SR | 18% |
| MP miss rate | 50% |
| Description | Borderline VP, no sidecar reinforcement |

**Assessment:** This is the weakest-signal zone. 50% of these races are lost to mid-price winners. Shadow flag should lower operator confidence in the pick.

---

## Data Limitations

### Per-runner sidecar scores not stored in verdict JSON

The verdict JSON only stores the **top pick's** sidecar scores. To compute delta features (winner MDS − top MDS, winner improvement − top improvement), the winner's per-runner prediction data is required.

Current status: the winner's VP, MDS, improvement, and place_prob at race time are **not available** for retrospective analysis when the winner was not the top pick. This is the primary forensic gap.

**Impact on Phase 2 delta table:** The full delta feature table (as specified in Issue #78) cannot be computed from current stored data. Winner-side signals are missing. The comparison table in this document uses only top-pick signals.

### Fields not stored in verdict JSON

| Field | Coverage in verdict JSON | Doctrine status | Forensic impact |
|---|---|---|---|
| `postdata_score` | **0%** | STORED_ONLY (Supabase `velo_verdicts`) | Cannot audit from verdict JSONs |
| `is_postdata_pick` | **0%** | DISPLAY_ONLY | Cannot audit |
| `is_topspeed_pick` | **0%** | DISPLAY_ONLY | Cannot audit |
| `plot_conviction` | **0%** | TIER_GATE | Cannot audit |
| `spotlight_score` | 39% | SHADOW_ONLY | Partial coverage only |
| `rpdc_primary_tag` | 2% | DISPLAY_ONLY | Insufficient sample |
| `mark_compression_score` | 0% (not in top dict) | LIVE_SCORING | Cannot audit per-race |

**These fields exist in the RP data pipeline but are either not stored in the local verdict JSON or have low coverage in the historical period.** The RP intent signals (postdata pick, topspeed pick) that Issue #78 targets as "unused" are genuinely unused in the current verdict archive.

### AW track note

AW tracks (Southwell, Lingfield, Wolverhampton, Newcastle AW) account for **127/706 mid-price misses (18%)** despite being a minority of races. AW mid-price miss rate = 47% vs grass = 41%. AW is a secondary target for the mid-price suppressor.

---

## Coverage Summary — Field Availability

| Field | Coverage in MP miss dataset | Source |
|---|---|---|
| `top_vp` (velo_prime_prob) | 87% | verdict JSON |
| `top_mds` (market_deception_score) | 87% | verdict JSON |
| `top_improvement` (improvement_score) | 87% | verdict JSON |
| `top_place_prob` | 87% | verdict JSON |
| `winner_sp_dec` | 100% | results JSON |
| `winner_name` | 100% | results JSON |
| `tier` | 100% | verdict JSON |
| `course` | 100% | verdict JSON |
| `top_spotlight_score` | 39% | verdict JSON (partial — added mid-period) |
| `top_cash_run_flag` | 61% | verdict JSON (partial) |
| `top_rpdc_release_score` | 64% | verdict JSON (partial) |
| `top_postdata_score` | **0%** | NOT in verdict JSON |
| `top_is_postdata_pick` | **0%** | NOT in verdict JSON |
| `top_is_topspeed_pick` | **0%** | NOT in verdict JSON |
| `top_plot_conviction` | **0%** | NOT in verdict JSON |
| `winner_mds` | **0%** | NOT STORED (per-runner data not in verdicts) |
| `winner_improvement` | **0%** | NOT STORED |
| `winner_vp` | **0%** | NOT STORED (only top pick VP stored) |

---

## Phase 1 Conclusions

### Finding 1 — Scale confirmed

706 mid-price misses (SP 3.0–8.5) = 54.3% of all confirmed misses across 40 race days. The 3.0–5.0 sub-band alone is 59% of mid-price misses. This is the dominant loss channel.

### Finding 2 — MDS is the primary discriminant

Market deception score on the top pick is **2.7× higher in wins than in mid-price misses** (0.173 vs 0.064). When MDS ≥ 0.30 at VP ≥ 0.30, mid-price miss rate drops to 18% and SR rises to 55%. Only 4% of mid-price misses had top pick MDS > 0.30.

**Current doctrine status:** MDS is LIVE_SCORING (10% weight in active ensemble). This finding validates that MDS weight is correct — the problem is that most mid-price miss races have LOW MDS on the top pick, not that MDS is absent from the model.

### Finding 3 — The gap is winner-side signals, not top-pick signals

The system correctly detects deception when MDS fires. When it doesn't fire (89% of mid-price misses), the winner had something the system didn't compare. The winner's MDS, improvement, and mark_compression at race time are not available for retrospective analysis. Phase 2 cannot compute the full delta table without per-runner score storage.

### Finding 4 — RP intent fields are blind spots in the verdict archive

`postdata_score`, `is_postdata_pick`, `is_topspeed_pick`, `plot_conviction` have **0% coverage** in the verdict JSON archive. These RP intent signals cannot be audited forensically from current data. To make them actionable for Mid-Price Hunter, they would need to be added to the verdict JSON output (a scoring-path change — requires separate issue and doctrine review).

### Finding 5 — Tier A is the highest-damage zone

73 Tier A mid-price misses with avg VP=0.411 and avg winner SP=4.87. These are high-conviction picks beaten by second-priced runners. 67% of the winners were priced 3.0–5.0. This is the primary suppression target.

---

## Phase 5 Pre-conditions

Before `src/velo/midprice_hunter.py` can be built, two pre-conditions must be satisfied:

### Pre-condition 1 — Per-runner score storage (required for Phase 2 delta table)

**Problem:** Winner-side sidecar scores (MDS, improvement, VP at race time) are not available for retrospective analysis. The verdict JSON stores only the top pick.

**Resolution option A:** Add all scored runners (not just top) to the verdict JSON output. This is a pipeline change, not a scoring change.

**Resolution option B:** Accept the limitation and build `midprice_hunter.py` using only top-pick signals (Rule 2 and Rule 4 from Phase 4). This is buildable now without pipeline changes.

**Recommendation:** Build Phase 5 with top-pick signals only (Option B). Per-runner storage is a separate enhancement issue.

### Pre-condition 2 — Shadow rule validation (n≥30 forward shadow)

Phase 4 rules are based on historical forensic evidence (retrospective). Before any rule is promoted beyond shadow, it must accumulate ≥30 forward observations with outcome closed.

**Current state:** 0 forward observations — Phase 5 module will begin accumulation.

---

## Immediate Next Steps

1. **Build `src/velo/midprice_hunter.py`** (Phase 5) — using top-pick signals only per Pre-condition 1 Option B
2. **Create shadow ledger** `data/midprice_shadow_ledger.csv`
3. **Wire into `run_prime_today.py`** after `score_race_velo_prime()` returns — shadow-only, no scoring side effects
4. **Accumulate forward observations** — target n=30 per rule before any Phase 4 assessment
5. **Separate issue for per-runner score storage** — to enable the full Phase 2 delta table in a future sprint

---

## Non-negotiables (repeated from Issue #78)

- No live scoring changes
- No ensemble weight changes
- No execution changes
- No routing-to-execution changes
- Shadow ledger only
- Evidence before promotion
- Respect `docs/engineering/VELO_FIELD_TO_DECISION_MAP.md`
