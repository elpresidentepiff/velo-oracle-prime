# VÉLØ PRIME — MODULE SPECIFICATION
## Plot Hunter + Intent Classification Engine + Race Regime Override Layer
### Version 1.0 | Build-Ready Specification

> This document specifies three interlocking layers to be built into VÉLØ PRIME as hard operational code. These are not optional refinements. They are structural corrections to a known failure mode.

---

## LAYER 1 — PLOT HUNTER (PJI Engine)

### 1.1 Core Concept

A finishing position is not evidence of effort level. The Plot Hunter's job is to reconstruct **effort intent** from observable signals and determine whether the visible result represents the horse's true output or a managed performance.

Every runner in every analysed race receives a **Plot Job Index (PJI)** score from 0 to 100.

---

### 1.2 PJI Score Components

#### Component A — Concealed Effort Score (0–20)
Did the horse finish with more in reserve than its position suggests?

| Signal | Points |
|---|---|
| Travelled well to 2-out / 1-out, then hands-and-heels only | +5 |
| No hard drive applied when chance had gone | +4 |
| Stayed on into frame position without urgency | +4 |
| Finished with energy while rivals were fully ridden out | +4 |
| Jockey visibly eased horse well before line | +3 |

#### Component B — Setup Mismatch Score (0–20)
Was this run designed to lose?

| Signal | Points |
|---|---|
| Trip demonstrably wrong (>3f short or long of proven optimum) | +5 |
| Ground at least 2 going bands outside proven range | +4 |
| Track configuration against running style | +3 |
| Pace shape directly against horse's mode | +3 |
| Wide/traffic/worst draw in field | +2 |
| Non-first-choice jockey / amateur / claiming rider | +3 |

#### Component C — Handicap Preservation Score (0–20)
Did this run serve a mark-management purpose?

| Signal | Points |
|---|---|
| Repeated 4th–8th finishes without mark rising | +5 |
| Beaten within "safe" distance (within 4–6 lengths, never challenging) | +4 |
| Shaped better than result but not "embarrassingly" better | +4 |
| Returns off same OR or lower OR despite competitive shape | +4 |
| Quick return (10–20 days) to similar conditions off same mark | +3 |

#### Component D — Jockey Intent Switch Score (0–15)
Does the jockey booking signal a change of intent?

| Signal | Points |
|---|---|
| Return of yard's first-choice rider | +6 |
| Step up in jockey quality | +5 |
| Jockey known for landing yard's handicap touches | +4 |

#### Component E — Market Resistance Score (0–15)
Is the market refusing to abandon a horse the form book says is beaten?

| Signal | Points |
|---|---|
| Horse drifts less than 20% despite ugly recent form | +5 |
| Persistent early support before race despite public negatives | +4 |
| Late firmers on a horse with no obvious public reason | +4 |
| Previous supported run was never placed in race / jockey never asked | +2 |

#### Component F — Release-Day Alignment Score (0–10)
Have the conditions now aligned with the horse's known kill zone?

| Signal | Points |
|---|---|
| Returns to last winning trip (within 1f) | +3 |
| Returns to last winning going (within 1 band) | +3 |
| Same class level as last winning run | +2 |
| Same track type as last winning run | +2 |

---

### 1.3 PJI Classification Table

| Score | Classification | Action |
|---|---|---|
| 0–24 | **DEAD** | No signal. Standard analysis only. |
| 25–49 | **WATCHLIST** | Monitor. Flag for next run review. |
| 50–69 | **LIVE ANOMALY** | Include in chassis consideration. Note in output. |
| 70–84 | **STORED BULLET** | Auto-include in Top-4 containment. Upgrade in any handicap. |
| 85–100 | **RELEASE CANDIDATE** | Override normal chassis order. Moves to Sword or Anchor regardless of market. |

---

### 1.4 Plot Memory Spine — Per-Runner Data Fields

```
runner_id
race_id
finish_position
sp
in_running_position [2f_out, 1f_out, line]
travel_quality_score        // 1–5 (1=struggling, 5=cantering)
urging_intensity_score      // 1–5 (1=hands only, 5=fully driven)
passage_efficiency          // 1–5 (1=blocked/wide throughout, 5=perfect run)
pace_suitability            // IDEAL | ACCEPTABLE | AGAINST
trip_suitability            // IDEAL | ACCEPTABLE | WRONG
ground_suitability          // IDEAL | ACCEPTABLE | WRONG
or_before_run
or_after_run
or_movement                 // numeric: negative = drop, positive = rise
jockey_this_run
jockey_next_run
jockey_quality_change       // UPGRADE | SAME | DOWNGRADE
days_to_next_run
headgear_change_next_run    // boolean
market_move_next_run        // FIRM | HOLD | DRIFT
pji_score
pji_classification
result_next_run
```

---

### 1.5 Plot Sequence Pattern Detection

**Sequence Type 1: The Classic Two-Run Build**
```
Run N:   PJI ≥ 50 AND setup_mismatch ≥ 10 AND or_movement ≤ 0
Run N+1: release_day_alignment ≥ 6 AND jockey_quality_change = UPGRADE AND market_move = FIRM
OUTPUT: "DOUBLE-RUN RELEASE PATTERN DETECTED"
```

**Sequence Type 2: The Three-Run Education Cycle**
```
Run N:   PJI ≥ 40 AND finish_position > 4
Run N+1: PJI ≥ 40 AND finish_position > 4 AND or_movement ≤ 0
Run N+2: release_day_alignment ≥ 6
OUTPUT: "THREE-RUN EDUCATION CYCLE COMPLETING"
```

**Sequence Type 3: The Single Disguise**
```
Run N:   concealed_effort ≥ 12 AND setup_mismatch ≥ 12 AND or_movement < 0
Run N+1: release_day_alignment ≥ 7 AND market_resistance ≥ 8
OUTPUT: "SINGLE-RUN DISGUISE — HIGH CONFIDENCE RELEASE"
```

---

## LAYER 2 — DAY CLASSIFICATION ENGINE

### 2.1 The Only Question That Matters

Before any TS, RPR, OR, or market analysis is applied to a runner, the engine must force a classification:

> **Is today a CASH day, a SETUP day, or a DISGUISE day for this horse?**

This runs for every single runner before any other output is generated.

---

### 2.2 Day Type Definitions

#### CASH DAY
All conditions align. The yard wants this horse to win today.

**All must be true:**
- Trip suitability = IDEAL
- Ground suitability = IDEAL
- Jockey = first-choice or meaningful upgrade
- OR = at or below last winning OR
- Market = HOLD or FIRM
- No significant Setup Mismatch score
- No recent education run pattern

**Output tag:** `DAY_TYPE: CASH`

#### SETUP DAY
Running to gain fitness, experience, or to school. Winning is not the primary objective.

**Signals:**
- First run back after 60+ days off
- Trip or ground not ideal but not extreme wrong
- Standard/acceptable jockey booking
- OR neutral or slightly unfavourable
- Market showing no conviction

**Output tag:** `DAY_TYPE: SETUP`

#### DISGUISE DAY
The run is structured to minimise mark exposure. The horse will not be fully asked.

**Any 3+ of the following trigger DISGUISE:**
- Setup Mismatch score ≥ 12
- Non-first-choice jockey with no upgrade rationale
- OR rising into awkward territory (above recent winning mark by 5+)
- Race conditions directly against horse's profile
- In-running behaviour previously showed concealment (PJI ≥ 50 on prior run)
- Horse is in a position race for a bigger future target

**Output tag:** `DAY_TYPE: DISGUISE`

---

### 2.3 Day Type Integration Rules

| Day Type | Effect on Analysis |
|---|---|
| CASH | Normal full analysis applies. Horse is live. |
| SETUP | Downgrade finishing position expectations. Do not include in win chassis unless also PJI ≥ 70. Include in watchlist only. |
| DISGUISE | Override any positive market/ratings signal. Do not include in win chassis. Log into Plot Memory Spine for future tracking. |

**Hard Rule:** A DISGUISE day classification cannot be overridden by TS, RPR, OR, market move, or any ratings metric. The classification holds.

---

## LAYER 3 — RACE REGIME OVERRIDE

### 3.1 Race Regime Classification by Distance

| Code | Distance Band | Regime Name |
|---|---|---|
| SP | Up to 2m1f | SPEED RACE |
| MR | 2m1f – 2m5f | MID-RANGE RACE |
| ST | 2m5f – 3m1f | STAYING RACE |
| MA | 3m1f+ | MARATHON RACE |

---

### 3.2 Metric Weighting by Regime

#### SPEED RACE (SP)
- TS weight: HIGH (primary driver)
- RPR weight: MEDIUM
- Stamina assessment: NOT APPLIED
- Survivability weight: LOW

#### MID-RANGE RACE (MR)
- TS weight: MEDIUM
- RPR weight: MEDIUM
- Stamina assessment: MEDIUM
- Survivability weight: MEDIUM
- Pace suitability: HIGH

#### STAYING RACE (ST)
- TS weight: LOW — SUPPORTING EVIDENCE ONLY
- RPR weight: MEDIUM
- Stamina assessment: HIGH (primary driver)
- Survivability weight: HIGH (primary driver)
- Pace suitability: HIGH
- TS hard cap: TS figures from SP or MR distance NOT transferable as primary evidence

#### MARATHON RACE (MA)
- TS weight: BLOCKED — not permitted as primary selection driver
- RPR weight: LOW — used for ceiling check only
- Stamina assessment: PRIMARY DRIVER
- Survivability weight: PRIMARY DRIVER
- Jumping accuracy: HIGH (jump races only)
- Rhythm/attrition score: HIGH
- TS hard cap: TS from non-staying distances DISCARDED

---

### 3.3 Hard Block Rules (Non-Overridable)

**Rule S1:** In any ST or MA race, a horse whose best TS figure was recorded over SP distance cannot be ranked #1 or #2 in the chassis on the basis of that figure alone.

**Rule S2:** In any ST or MA race, if a horse's only evidence of a high TS comes from a SP or MR race, that figure must be tagged `TS_DISTANCE_INVALID` and suppressed from the primary ranking logic.

**Rule S3:** In any ST or MA race, a horse ranked in the top 2 of the chassis MUST have demonstrated staying evidence — at least one run at the target distance or within 4 furlongs of it — or the output must include: `WARNING: NO STAMINA EVIDENCE AT THIS TRIP`.

**Rule S4:** In MA races (3m1f+), the TS metric is not permitted to appear in the SWORD or ANCHOR slot justification. The system must use stamina, survivability, and course-trip conversion as the justification text.

---

### 3.4 Stamina Assessment Score (ST and MA races)

```
prior_win_at_trip          // has won at this distance or within 3f: +25
placed_at_trip             // placed at this distance or within 3f: +15
ran_creditably_at_trip     // ran at trip, finished respectably: +10
no_trip_evidence           // never run at this distance: 0
failed_at_trip             // ran at trip and clearly failed to stay: -20
staying_pedigree           // dam sire / sire known stayer: +5
strong_finish_pattern      // ran on late in most recent 3 runs: +10
weak_finish_pattern        // faded in final 2f in most recent 3 runs: -15
festival_hill_evidence     // specific Cheltenham finish-up-hill evidence: +10
```

| Score | Label | Output Effect |
|---|---|---|
| 40+ | PROVEN STAYER | Full chassis eligibility in ST/MA |
| 20–39 | POSSIBLE STAYER | Chassis eligible with caveat flag |
| 0–19 | STAMINA UNKNOWN | Must carry `UNPROVEN AT TRIP` flag |
| Below 0 | STAMINA DOUBT | Cannot rank in top 2. Must carry `LIKELY NON-STAYER` flag |

---

### 3.5 Survivability Score

```
consistent_finish_pattern          // top-4 in 3+ of last 5 starts: +15
battle_tested_form                 // ran in 18+ runner field: +5
big_field_competitiveness          // placed in field of 16+: +5
jumping_accuracy_clean             // no falls/unseated in last 6 starts: +10
jumping_accuracy_concern           // 1 fall or UR in last 6 starts: -5
jumping_accuracy_serious_concern   // 2+ errors in last 6 starts: -15
ground_handling_proven             // won in going within 1 band of today: +10
ground_handling_question           // no run in today's going type: 0
ground_handling_negative           // ran poorly in similar going: -10
festival_pressure_evidence         // ran competitively at Cheltenham or equiv: +10
finishing_energy                   // stayed on late without urgency (PJI signal): +5
fade_pattern                       // weakened into last 2 furlongs in 2+ recent runs: -10
```

| Score | Label |
|---|---|
| 40+ | HIGH SURVIVABILITY |
| 20–39 | MODERATE SURVIVABILITY |
| 0–19 | SURVIVABILITY RISK |
| Below 0 | SURVIVABILITY FAILURE — cannot anchor chassis |

---

## INTEGRATION MAP

```
INPUT: Race data received

STEP 1 — REGIME OVERRIDE LAYER
  → Classify race distance regime (SP / MR / ST / MA)
  → Set metric weights
  → Apply hard block rules

STEP 2 — DAY CLASSIFICATION ENGINE
  → For each runner: classify DAY_TYPE (CASH / SETUP / DISGUISE)
  → Apply Day Type integration rules
  → Remove DISGUISE runners from chassis
  → Flag SETUP runners as watchlist-only

STEP 3 — PLOT HUNTER
  → For each runner: calculate PJI score
  → Check Plot Memory Spine for sequence patterns
  → Apply RELEASE CANDIDATE override if PJI ≥ 85
  → Auto-include STORED BULLET (PJI 70–84) in chassis

STEP 4 — STANDARD VÉLØ ENGINE
  → Run Regime Classification (CLEAN / STANDARD / CHAOS / FCE)
  → Apply metric weights from Step 1
  → Apply Stamina Score for ST/MA races
  → Apply Survivability Score
  → Build chassis

STEP 5 — OUTPUT
  → Every runner tagged with:
      DAY_TYPE: [CASH/SETUP/DISGUISE]
      PJI: [score] [classification]
      STAMINA: [score] [label] (ST/MA only)
      SURVIVABILITY: [score] [label]
  → Chassis built under correct regime weighting
  → Hard block rules enforced
  → Release candidates flagged
```

---

## OUTPUT TAG REFERENCE

```
[DAY_TYPE: CASH]
[DAY_TYPE: SETUP]
[DAY_TYPE: DISGUISE]

[PJI: 78 — STORED BULLET]
[PJI: 91 — RELEASE CANDIDATE]
[PJI: 32 — WATCHLIST]
[PJI: 11 — DEAD]

[STAMINA: PROVEN STAYER]
[STAMINA: UNPROVEN AT TRIP]
[STAMINA: LIKELY NON-STAYER]
[TS_DISTANCE_INVALID — speed figure from shorter trip, suppressed]

[SURVIVABILITY: HIGH]
[SURVIVABILITY: RISK]
[SURVIVABILITY: FAILURE — chassis excluded]

[RELEASE PATTERN: DOUBLE-RUN RELEASE DETECTED]
[RELEASE PATTERN: THREE-RUN EDUCATION CYCLE COMPLETING]
[RELEASE PATTERN: SINGLE-RUN DISGUISE — HIGH CONFIDENCE]

[CHASSIS OVERRIDE: PJI ≥ 85 — promoted regardless of market]
[CHASSIS BLOCK: DISGUISE DAY — suppressed regardless of ratings]
[CHASSIS BLOCK: STAMINA FAILURE — cannot anchor]
[WARNING: NO STAMINA EVIDENCE AT THIS TRIP]
```

---

## HARD RULES SUMMARY

These rules must be enforced at the code level. They cannot be overridden by any prompt instruction, market data, or ratings input.

1. A DISGUISE DAY classification suppresses a runner from the win chassis regardless of TS, RPR, OR, or market move.
2. In ST and MA races, TS figures from SP or MR distances are tagged `TS_DISTANCE_INVALID` and suppressed from primary ranking logic.
3. No runner with `STAMINA: LIKELY NON-STAYER` may occupy the Anchor or Sword slot in an ST or MA race.
4. Any runner with `PJI ≥ 85` is auto-promoted to Sword or Anchor regardless of market position.
5. Any runner with `PJI ≥ 70` (STORED BULLET) must appear in the Top-4 chassis unless blocked by DISGUISE DAY or STAMINA FAILURE.
6. The Plot Memory Spine must log every runner after every race for retrospective pattern detection.
7. In MA races, the Anchor and Sword justification text must reference stamina and survivability evidence. The word "speed" or "TS" may not appear as the primary justification in these slots.
8. The Day Classification Engine runs before any other analysis module. It is the first gate.

---

*This document is intended for direct handoff to Manus for code integration into VÉLØ PRIME. All field names, score ranges, classification labels, and output tags should be treated as fixed specification unless a formal revision is issued.*
