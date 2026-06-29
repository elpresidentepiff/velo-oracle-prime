# Pattern Prosecutor Schema V1

**Status**: SCHEMA ONLY — no prosecution runs in Phase 1
**Created**: 2026-06-14
**Owner**: VÉLØ Forensics Unit

---

## Purpose

The Pattern Prosecutor tests whether VÉLØ's beliefs are statistically real.

A belief might be: "VP>=0.45 at Musselburgh wins at a high rate."
Or: "MID_PRICE_WALL misses repeat in Class 3-4 handicaps."
Or: "SETUP_DEPENDENT horses flagged by VFU outperform their VP score next time."

The Pattern Prosecutor does not create beliefs. It prosecutes them.

A belief that passes prosecution becomes **CONFIRMED_PATTERN** and enters the evidence base.
A belief that fails prosecution becomes **BELIEF_REJECTED** and must be dropped.
A belief under observation is **ACCUMULATING_EVIDENCE**.

The Pattern Prosecutor reads from:
- VFU Race Autopsy Ledger
- Sigma results universe
- Horse Passport forensic extensions
- Innovation protocol CSV

The Pattern Prosecutor writes to:
- Pattern Evidence Ledger (local, `data/reports/vfu_pattern_ledger/`)

The Pattern Prosecutor does NOT write to:
- Supabase
- Sigma rows
- Model weights
- Scoring formula

---

## Pattern Record Schema

```json
{
  "pattern_id":       "string — slug, e.g. VP45_MUSSELBURGH_WIN_RATE",
  "belief":           "string — the claim being tested",
  "source":           "VFU_AUTOPSY | SIGMA_OBSERVATION | OPERATOR_HYPOTHESIS",
  "created":          "YYYY-MM-DD",

  "filter_criteria": {
    "vp_min":         "float or null",
    "vp_max":         "float or null",
    "gate_labels":    ["GREEN", "AMBER", "RED"],
    "courses":        ["string or null"],
    "race_types":     ["string or null"],
    "going_codes":    ["string or null"],
    "distance_band":  "string or null",
    "odds_band":      "string or null",
    "class_band":     "string or null",
    "failure_classes": ["string or null"],
    "current_state_labels": ["string or null"]
  },

  "evidence": {
    "n":              "integer — total races matching filter",
    "wins":           "integer",
    "places":         "integer",
    "misses":         "integer",
    "win_sr":         "float",
    "place_sr":       "float",
    "date_range":     "YYYY-MM-DD to YYYY-MM-DD",
    "courses_covered": ["string"],
    "odds_bands_covered": ["string"],
    "vp_bands_covered": ["string"]
  },

  "minimum_sample_size": "integer — n needed to adjudicate",
  "verdict_threshold": {
    "pass_win_sr":    "float — win SR needed to CONFIRM",
    "fail_win_sr":    "float — win SR below which REJECT",
    "observe_window": "integer — n before first verdict"
  },

  "status":           "ACCUMULATING_EVIDENCE | CONFIRMED_PATTERN | BELIEF_REJECTED | UNDER_REVIEW",
  "verdict":          "PASS | FAIL | OBSERVE | INCONCLUSIVE or null",
  "verdict_date":     "YYYY-MM-DD or null",

  "upgrade_recommendation":   "string or null",
  "downgrade_recommendation": "string or null",
  "human_approval_required":  "boolean",

  "linked_autopsy_ids":   ["string"],
  "linked_horse_ids":     ["integer"],

  "last_updated":     "ISO8601 UTC timestamp",
  "provenance":       "PATTERN_PROSECUTOR_V1"
}
```

---

## Verdict Thresholds (defaults — operator can override per pattern)

| Sample Size | Window |
|---|---|
| < 20 | OBSERVE — no verdict |
| 20-49 | First verdict possible — CONFIRM or REJECT against thresholds |
| 50-99 | Intermediate check |
| 100+ | Full adjudication |

Conviction threshold (default): Win SR >= baseline + 10pp = CONFIRM
Rejection threshold (default): Win SR < baseline - 5pp at n>=20 = REJECT

Baseline = current-era overall SR (24.3% as of 2026-06-14).

---

## Phase Rules

- Phase 1: Schema only. No prosecution runs.
- Phase 5: First Pattern Prosecutor summary report on VFU autopsies.
- No pattern can be promoted to doctrine without operator approval.
- No pattern can alter VP thresholds, model weights, or scoring formula.
