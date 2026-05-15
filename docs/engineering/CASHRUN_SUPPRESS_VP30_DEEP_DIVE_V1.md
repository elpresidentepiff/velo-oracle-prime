# CASHRUN SUPPRESS+VP30 DEEP DIVE V1

## Status

```
CASHRUN: OPERATOR_VISIBILITY_ONLY
This document: ANALYTICAL FRAMEWORK ONLY
Activation: NO
Weight changes: NO
Scoring changes: NO
```

---

## The Pattern

From CASHRUN Activation Audit V1 (2026-05-15, n=2,543 rows, 52 dates):

```
SUPPRESS + VP30 cohort:
  n=26 rows, 17 results
  SR = 58.8%
  ROI = +0.699
  
All VP30 baseline (unified evidence audit, n=345):
  SR = 32.2%
  
SUPPRESS+VP30 outperforms all-VP30 by +26.6pp SR.
```

**The central question:** Why does VÉLØ win where CASHRUN says suppress?

---

## What CASHRUN SUPPRESS Means

A horse receives SUPPRESS when one or more of the following applies:

1. **plot_conviction < threshold** — No convincing trainer plot signal in the RP racecard
2. **handicap_plot_score low** — The horse's rating trajectory and mark context don't suggest a competitive handicap angle
3. **trainer_form = negative** — Trainer recent strike rate is below par
4. **NEGATIVE_CLAIM tag present** — Spotlight text contains phrases like "others preferred", "hard to recommend", "well beaten", "opposable"
5. **WEAK_SIGNAL aggregate** — Multiple weak signals combine below the WATCH threshold

SUPPRESS does not mean the horse cannot win. It means trainer-intent evidence is absent or negative.

---

## What VP≥0.30 Means

VP (VÉLØ Prime) ≥ 0.30 means:
- SQPE model assigns high structural probability
- Improvement score may be elevated (form trajectory)
- Market deception score may be elevated (smart money)
- The ensemble has found a reason to be confident that trainer intent signals do not provide

**Key insight:** VÉLØ's signals are orthogonal to CASHRUN's signals. VÉLØ doesn't read Spotlight text or plot conviction. CASHRUN doesn't read SQPE outputs or market deception scores.

---

## Why the Pattern Makes Sense

When a horse is VP≥0.30 AND CASHRUN SUPPRESS, it is:

1. **Structurally strong in VÉLØ's model** (form, ratings, conditions)
2. **Silent in trainer-intent space** (no plot, no stable fancy tag, maybe negative trainer form)

These are not contradictions. They are different information sources. The most likely explanations:

### A — Low-Profile Horse, High-Value Market

The trainer is not telegraphing. There is no RP plot claim. But:
- The horse is well-placed on ratings (SQPE sees this)
- The horse may be dropping in class or returning to preferred conditions (improvement_score)
- Smart money has moved the price (market_deception_score)

CASHRUN reads silence and calls it SUPPRESS. VÉLØ reads structure and rates it VP≥0.30.
The horse wins because VÉLØ was right about the structure.

### B — CASHRUN Suppress Rules Are Too Aggressive

CASHRUN may be penalising trainer-plot absence even when the horse has structural advantages
that make the absence irrelevant. If a horse is well-handicapped and the market agrees, trainer
intent is a redundant signal — not a negative one.

The current SUPPRESS rules treat "no trainer plot" as a warning. It may be neutral.

### C — RP Coverage Artefact

Some horses simply don't generate a Spotlight plot claim because they're new, returning from
a long absence, or in race types RP covers less thoroughly. CASHRUN reads thin coverage as
low conviction. VÉLØ is unaffected by RP coverage depth.

---

## How to Investigate — Query Design

### Query 1: What Was the Suppress Rule for Each Winner?

For each SUPPRESS+VP30 horse that won, extract:

```
cashrun_class | plot_conviction | handicap_plot_score | trainer_form | claim_tags
```

If 80% of winners had `plot_conviction < threshold` but positive `going_flag` and `ability_flag`,
Hypothesis A is supported (low-profile, structurally solid).

If 80% of winners had `trainer_form = negative`, Hypothesis B is supported (trainer form
rule is miscalibrated for VP≥0.30 horses).

### Query 2: What Were the VP Components for These Horses?

For each SUPPRESS+VP30 horse that won, extract:

```
improvement_score | market_deception_score | sqpe_v17 score | place_prob
```

If `market_deception_score > 0.5` appears frequently in the winner group, the disagree-and-win
pattern is driven by MDS (smart money overriding plot silence). This is the strongest version
of the pattern and has direct implications for CASHRUN/VÉLØ integration design.

### Query 3: Price Band Profile

```python
# Group SUPPRESS+VP30 results by SP band:
# < 3.0 | 3.0-5.0 | 5.0-8.5 | 8.5-15.0 | > 15.0
```

If winners are concentrated in the 5.0-8.5 band, this is mid-priced structural value —
exactly the segment that is the system's primary unsolved miss class.
This would confirm that CASHRUN is suppressing the very horses VÉLØ most needs.

### Query 4: Race Type and Trainer Profile

```python
# Split by: Flat vs NH, Handicap vs Non-Handicap, trainer_form label
```

If the pattern is concentrated in handicap races (where trainer intent matters most to CASHRUN),
the SUPPRESS rules are specifically miscalibrated for handicap structural value picks.

---

## Suppression Rule Sensitivity Analysis

Current SUPPRESS thresholds (estimated from CASHRUN detector logic):

| Rule | Threshold | Effect |
|---|---|---|
| `plot_conviction` | < 0.15 | Suppresses most NH and low-profile Flat horses |
| `handicap_plot_score` | < 0.20 | Suppresses horses not near a winning mark |
| `trainer_form` | negative | Penalises trainer-form absence even at VP≥0.30 |
| `NEGATIVE_CLAIM` | any | Spotlight pessimism → suppress |

**Hypothesis:** Relaxing the trainer_form suppress rule for VP≥0.30 horses would recover
the SUPPRESS+VP30 cohort without changing the WATCH/READY thresholds.

This is a future option — not current policy.

---

## What CASHRUN Should NOT Do Based on This Finding

```
Must not suppress VP≥0.30 horses based on trainer_form alone
Must not treat Spotlight NEGATIVE_CLAIM as a hard gate for VP≥0.30 horses
Must not treat plot_conviction < threshold as equivalent to "horse won't win"
```

These are analytical conclusions, not policy changes. They inform the design of
future CASHRUN V2 rules if the SUPPRESS+VP30 pattern holds at n≥200.

---

## Sample Size Reality Check

```
n=17 results is too small for stable conclusions.
A variance analysis at avg SP unknown:
  - If avg SP = 8.0 (fair odds for SUPPRESS bucket), 17 wins from ~29 runners
    implies extraordinary outperformance that is almost certainly not sustainable
  - If avg SP = 4.0, 17 wins from ~29 runners is high but plausible SR territory

ROI=+0.699 is striking but could be driven by 2-3 big-SP winners.
Do not draw policy conclusions until n≥50 results.
```

---

## Audit Trigger

Build the dedicated disagree query when:
- n ≥ 50 SUPPRESS+VP30 results (currently 17)
- At current accumulation rate (~0.5/day), trigger in ~60+ race days
- Estimated date: late July 2026 if May–July scoring continues

---

## Integration Design (future, not current)

If the pattern holds at n≥200:

**Option A — Suppress Relaxation Gate**
For VP≥0.30 horses, relax the trainer_form suppress rule.
Horses with VP≥0.30 that would otherwise be SUPPRESS are reclassified as WEAK_SIGNAL.
CASHRUN remains the gatekeeper — the rule threshold is calibrated, not removed.

**Option B — Disagreement Signal**
Add a `CASHRUN_VELO_DISAGREE` flag to the daily report.
This flag is informational only: "VÉLØ rates this horse highly but CASHRUN suppresses it."
Operator can use this as a filter or investigation trigger.

**Option C — Orthogonal Layer**
Treat CASHRUN and VÉLØ as parallel signal streams.
The combination VP≥0.30 + CASHRUN_SUPPRESS becomes its own evidence bucket,
not an override of CASHRUN's verdict.

None of these options activate in V1. They are design vocabulary for the future.

---

## Version History

| Version | Date | Notes |
|---|---|---|
| V1 | 2026-05-15 | Initial deep dive. n=17 results. Three hypotheses. Four query designs. |
