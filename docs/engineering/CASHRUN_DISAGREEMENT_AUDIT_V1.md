# CASHRUN DISAGREEMENT AUDIT V1

## Purpose

Design document for a dedicated audit of the CASHRUN / VÉLØ disagreement pattern.
Specifically: why do horses CASHRUN suppresses but VÉLØ scores VP≥0.30 appear to win
at above-baseline rates? This audit does not activate CASHRUN. It does not change
weights, router, staking, or any scoring rule. It is evidence design only.

## Classification

```
CASHRUN status: OPERATOR_VISIBILITY_ONLY
This audit: EVIDENCE_DESIGN
Activation: NO
Weight changes: NO
Router changes: NO
```

---

## The Finding That Prompted This Audit

From `CASHRUN_ACTIVATION_AUDIT_V1.md` (2026-05-15, n=2,543 rows):

| Signal | n | Results | SR | ROI |
|---|---|---|---|---|
| SUPPRESS + VP30 | 26 | 17 | 58.8% | +0.699 |
| Any + VP30 | 31 | 20 | 55.0% | +0.719 |
| WATCH + VP30 | 0 | 0 | — | — |

The SUPPRESS + VP30 group:
- CASHRUN scores these horses SUPPRESS (trainer plot logic is absent or negative)
- VÉLØ scores these horses VP≥0.30 (structural model confidence is high)
- They win at 58.8% SR, ROI=+0.699

This is the disagree-and-win pattern. n=26 is not definitive, but the signal is
striking enough to warrant a structured audit before accumulating 50+ more results
with no analytical framework.

---

## Why This Pattern Exists — Two Hypotheses

### Hypothesis 1: CASHRUN Suppress Rules Are Miscalibrated

CASHRUN's SUPPRESS bucket is primarily driven by:
- Absence of trainer intent signals (no plot conviction, no stable fancy tag)
- Low handicap plot score
- Negative trainer form
- NEGATIVE_CLAIM tags in Spotlight

These rules penalise trainer-plot silence heavily. A horse can be structurally
excellent — high OR, rising form trend, correct going, strong ability flags,
market-backed — and still receive SUPPRESS if no trainer intent is visible in
the RP source data.

If this hypothesis is correct, the SUPPRESS rule is a false negative generator
for horses where VÉLØ's structural model correctly finds value that the RP
trainer-plot layer cannot see.

### Hypothesis 2: VÉLØ Is Correctly Identifying a Different Value Dimension

VÉLØ's VP score is driven by the SQPE ensemble, improvement score, and market
deception score. None of these depend on trainer intent. They measure:
- Model confidence in the outcome probability
- Evidence of form improvement
- Market asymmetry (smart money vs public)

A VP≥0.30 horse that CASHRUN suppresses may simply be a horse the market values
(or that the model values) for structural reasons that RP's plot-based commentary
doesn't surface. The horse may have no visible trainer intent because the trainer
doesn't telegraph — not because the horse isn't trying.

If this hypothesis is correct, the disagreement layer is a feature, not a bug.
CASHRUN's absence of trainer-intent is informative about RP coverage, not about
the horse's likelihood.

---

## What the Audit Should Measure

### Query 1 — SUPPRESS+VP30 Horse Profile

For each SUPPRESS + VP30 horse that produced a result:

| Field to extract | Purpose |
|---|---|
| `cashrun_class` | Confirm SUPPRESS |
| `vp_score` | Confirm VP≥0.30 |
| `plot_conviction` | Was there any trainer plot signal at all? |
| `handicap_plot_score` | How far below the SUPPRESS gate did this horse score? |
| `trainer_form` | Was suppress driven by negative trainer form? |
| `claim_tags` | Were NEGATIVE_CLAIM tags present? |
| `consensus_signals` | Were RP structural flags positive? |
| `or_trend` | Was the horse rising in the ratings? |
| `ts_trend` | Was topspeed improving? |
| `going_flag`, `distance_flag`, `course_flag` | Were conditions correct? |
| `improvement_score` | Was VÉLØ improvement signal elevated? |
| `market_deception_score` | Was smart money visible? |
| `avg_sp` | Are these horses value or short-priced? |

This profile tells us: are these horses being suppressed for the wrong reason,
or are they genuinely blank on trainer intent but structurally strong?

### Query 2 — SUPPRESS Rule Breakdown

For the 26 SUPPRESS+VP30 horses, extract which SUPPRESS rules were triggered:

| Suppress rule | n triggered | Win rate for rule-triggered horses |
|---|---|---|
| plot_conviction < threshold | ? | ? |
| trainer_form = negative | ? | ? |
| NEGATIVE_CLAIM present | ? | ? |
| handicap_plot_score < threshold | ? | ? |

If one rule dominates and that rule's cohort wins at elevated rates, that rule
is the miscalibration candidate.

### Query 3 — Confidence Calibration

Compare SUPPRESS+VP30 to the overall VP≥0.30 population:

| Cohort | n | SR | ROI | Avg VP |
|---|---|---|---|---|
| SUPPRESS + VP30 | 26 | 58.8% | +0.699 | ? |
| All VP≥0.30 (from unified audit) | 345 | 32.2% | ? | 0.30+ |
| Tier A + VP≥0.30 | 162 | 40.1% | ? | 0.425 |

If SUPPRESS+VP30 SR outperforms Tier A, the disagreement layer is a stronger
signal than the base ensemble at the same VP floor. That would be a significant
finding.

### Query 4 — WATCH+VP30 Absence

WATCH+VP30 = 0 across 2,543 rows. This means:
- CASHRUN has never confirmed a VP≥0.30 horse
- The two systems are operating on orthogonal signal dimensions

This rules out CASHRUN as a VP30 booster in V1. It is the most important
negative finding: if CASHRUN cannot agree with VÉLØ on a single high-VP horse
across 52 race days, the systems are not measuring the same thing.

---

## What This Audit Must NOT Do

```
Must not activate CASHRUN_WATCH as a signal
Must not activate CASHRUN SUPPRESS as a filter or gate
Must not modify VP score thresholds
Must not modify router rules
Must not change staking logic
Must not change CASHRUN scoring rules
Must not change CASHRUN_READY or CASHRUN_WATCH definitions
CASHRUN remains OPERATOR_VISIBILITY_ONLY until a full activation review at n≥200
```

---

## Audit Output Design

### File

```
data/reports/cashrun_disagreement_audit_latest.json
data/reports/cashrun_disagreement_audit_latest.md
```

### Schema

```json
{
  "generated_at": "...",
  "audit_version": "CASHRUN_DISAGREEMENT_AUDIT_V1",
  "suppress_vp30_cohort": {
    "n": 26,
    "results": 17,
    "sr": 0.588,
    "roi": 0.699,
    "avg_sp": ...,
    "avg_vp": ...,
    "suppress_rule_breakdown": {
      "plot_conviction_below_threshold": { "n": ?, "sr": ? },
      "negative_trainer_form": { "n": ?, "sr": ? },
      "negative_claim_tag": { "n": ?, "sr": ? },
      "low_handicap_plot_score": { "n": ?, "sr": ? }
    },
    "structural_flag_profile": {
      "or_trend_rising": ?,
      "ts_trend_improving": ?,
      "going_flag_positive": ?,
      "distance_flag_positive": ?
    }
  },
  "comparison": {
    "all_vp30": { "n": ?, "sr": ?, "roi": ? },
    "tier_a_vp30": { "n": 162, "sr": 0.401, "roi": ? },
    "suppress_vp30": { "n": 26, "sr": 0.588, "roi": 0.699 }
  },
  "watch_vp30_absence": {
    "n": 0,
    "interpretation": "Systems operate on orthogonal signal dimensions"
  },
  "hypothesis_verdict": "INSUFFICIENT_SAMPLE | H1_CANDIDATE | H2_CANDIDATE | BOTH"
}
```

---

## Implementation Plan (future — not current)

| Step | Script | Trigger |
|---|---|---|
| 1 | Extend `cashrun_activation_audit.py` with a `--disagree-audit` mode | After n≥50 SUPPRESS+VP30 results |
| 2 | Extract CASHRUN CSV fields matched to adapter features | Requires adapter field backfill |
| 3 | Build SUPPRESS rule breakdown table | After step 1 |
| 4 | Compare to unified evidence audit VP30 cohort | After step 3 |
| 5 | Produce `cashrun_disagreement_audit_latest.json` | Human review gate |

Step 1 cannot run meaningfully until n≥50 SUPPRESS+VP30 results. Current n=17 results.
Estimated trigger: 30+ more days of scoring at current SUPPRESS+VP30 frequency (~0.5/day).

---

## Current Interpretation

```
CASHRUN SUPPRESS + VP30 = 26 rows, 17 results, SR=58.8%, ROI=+0.699

Status: STRIKING BUT UNVALIDATED
n=17 results is too small for stable ROI estimates at avg SP unknown
A handful of big-SP winners could explain the entire positive ROI
Do not draw operational conclusions yet

Hypothesis: CASHRUN suppress rules penalise trainer-plot absence too harshly
for horses that VÉLØ identifies via structural and market signals
Evidence: Not yet — need n≥50 results and rule breakdown

Next review trigger: n=50 SUPPRESS+VP30 results OR 30+ more race days
```

---

## Activation Gate (future — not current)

No CASHRUN activation is permitted before:

1. Dedicated disagree audit runs with n≥200 SUPPRESS+VP30 results
2. SR lift above All VP30 baseline confirmed at n≥200
3. Suppress rule breakdown identifies which rules produce false negatives
4. Human review of specific miscalibrated rules — not blanket SUPPRESS relaxation
5. Operator decision: CASHRUN suppress becomes a WARN flag, not a BLOCK, for VP≥0.30 horses

No automatic activation at any threshold. Operator decision required.

---

## Version History

| Version | Date | Changes |
|---|---|---|
| V1 | 2026-05-15 | Initial design. Based on SUPPRESS+VP30 finding from activation audit. n=17 results. |
