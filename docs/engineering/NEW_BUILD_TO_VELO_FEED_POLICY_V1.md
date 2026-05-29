# New Build → VELO Feed Policy V1

**Status:** ACTIVE  
**Effective:** 2026-05-29  
**Classification:** `NEW_BUILD_SIDECAR_FEED_READY / OLD_VELO_AUC_NOT_COMPARABLE_UNTIL_REPLAY / OUTCOME_EVAL_REQUIRED`

---

## 1. Purpose

This document defines the operating policy for the New Build paper model and its
relationship to Old VÉLØ. It governs what New Build output may be used for, what
it must never do, and what conditions must be met before any integration proceeds.

New Build is a parallel paper-scoring system. Its output is a **read-only sidecar
signal**. It is not a scoring input to Old VÉLØ. It does not generate live
selections. It does not trigger Telegram. It does not stake.

---

## 2. Current Classification

| System | Status |
|---|---|
| Old VÉLØ | LIVE — untouched |
| Shadow VÉLØ | LIVE — untouched |
| New Build Lane A (Core+Passport) | PAPER_OPERATIONAL — morning scoring, no live execution |
| New Build Lane B (Challenger V1) | PAPER_ONLY_NO_INTENT — intent coverage < 80% gate |
| New Build AUC vs Old VÉLØ | NOT_COMPARABLE — runner-level probs not captured |

---

## 3. What New Build Output Is

New Build produces a **NEW_BUILD_PAPER_SIGNAL** per runner per race. Each signal includes:

- `champion_rank` — rank within race (1 = model's top pick)
- `champion_probability` — win probability from operational lane model
- `passport_found` / `passport_strength_score` — Racing Post passport coverage
- `intent_coverage_flag` — whether Intent features are available (morning reads: always BELOW_GATE)
- `model_lane_used` — LANE_A_CORE_PASSPORT or LANE_B_CHALLENGER_V1
- `passport_coverage_flag` — STRONG / MODERATE / WEAK per race
- `rpr_violation_flag` — must always be False; non-zero = pipeline error

All records carry:
```
"paper_only": true,
"velo_scoring_allowed": false,
"live_velo_impact": false,
"shadow_velo_impact": false,
"new_build_signal_type": "NEW_BUILD_PAPER_SIGNAL",
"old_velo_untouched": true
```

---

## 4. What New Build Output Must Never Do

| Action | Status | Reason |
|---|---|---|
| Alter Old VÉLØ model weights | PROHIBITED | No model changes without promotion gate |
| Alter Old VÉLØ scoring pipeline | PROHIBITED | Pipeline untouched until promotion gate |
| Write to Old VÉLØ scoring tables | PROHIBITED | New Build has its own data paths |
| Send Telegram messages | PROHIBITED | No Telegram from New Build path |
| Stake or generate betting instructions | PROHIBITED | Paper signal only, no live execution |
| Override Old VÉLØ verdict for any race | PROHIBITED | Old VÉLØ verdicts are authoritative |
| Use same-race SP in morning model | PROHIBITED | Leakage — RPR/SP banned from features |
| Use RP comments or tip heat as features | PROHIBITED | Per operating constraints |
| Use JTC-D all-time cumulative stats | PROHIBITED | Confirmed temporal leakage (AUC 0.84 artifact) |
| Stack Lane B sidecars without individual validation | PROHIBITED | Each sidecar wins individually first |

---

## 5. Permitted Uses of New Build Output

| Use | Permitted | Notes |
|---|---|---|
| Read-only sidecar feed artifact | YES | `data/new_build/sidecar_feed/` |
| Paper dashboard display | YES | `/api/governed-card` — paper-only verdicts |
| Comparison against Old VÉLØ top picks | YES | `new_build_old_velo_comparison.py` — read-only |
| Alignment analysis (Old VELO in NB top-3) | YES | Indicative only |
| Strike rate / frame rate comparison | YES | Indicative only — not statistically valid until n >= 200 |
| Historical replay for AUC (future) | YES | After runner-level prob capture resolved |
| Promotion discussion | YES | After promotion gate conditions met |

---

## 6. Two-Lane Architecture

### Lane A — Core+Passport (30 features) — OPERATIONAL
- Model: `data/new_build/models/core_v0_or_passport/core_v0_or_passport_model.pkl`
- Features: Core (19 structural/OR features) + Passport (11 Racing Post profile features)
- Status: Operational for morning current-card reads
- Intent: Not included — median-fill for intent features would produce misleading scores

### Lane B — Challenger V1 (45 features) — PAPER_ONLY_NO_INTENT
- Model: `data/new_build/models/core_v0_or_passport_intent/model.pkl`
- Features: Core (19) + Passport (11) + Intent (15 historical race/horse pairs)
- Gate: Intent coverage >= 80% required to go operational
- Current state: Intent coverage = 0% for morning reads (historical pairs never match current-card)
- Classification: `PAPER_ONLY_NO_INTENT` until gate passes
- AUC on held-out test (2025): 0.6969

Lane B is NEVER used as the operational scoring source until the Intent coverage gate
passes on at least 5 consecutive race days. Morning-card scores from Lane B are stored
but labelled `PAPER_ONLY_NO_INTENT` and must not be treated as operational output.

---

## 7. AUC Comparison Policy

Old VÉLØ AUC and New Build AUC are **NOT directly comparable** under current conditions.

**Why:** AUC requires per-runner probability scores from both models on identical
race/runner populations with identical binary targets. Old VÉLØ verdict files store
only the top pick per race (`top.horse`, `top.velo_prime_prob`). Runner-level
probability distributions from Old VÉLØ are not captured.

**What is comparable today:**
- Top-1 strike rate (indicative — not statistically valid at n < 200 races)
- Alignment rate (Old VÉLØ top pick inside New Build top-3)
- OR baseline comparison (naive highest-rated horse vs model pick)

**What is required for valid AUC comparison:** See `data/new_build/reports/historical_replay_requirement.md`

**Status until resolved:** `OLD_VELO_AUC_NOT_COMPARABLE_UNTIL_REPLAY`

---

## 8. Promotion Gate

New Build will not be integrated into Old VÉLØ scoring until ALL of the following conditions
are met and an explicit operator promotion decision is made:

| Gate | Condition | Status |
|---|---|---|
| G-1 | n >= 200 closed races evaluated | NOT_MET (currently 0 closed) |
| G-2 | New Build SR statistically above OR baseline (p < 0.05) | NOT_MET |
| G-3 | New Build SR >= Old VÉLØ SR on identical race population | NOT_MET (Old VÉLØ absent for current dates) |
| G-4 | RPR violations = 0 across all evaluated dates | MET (0 violations on 2026-05-29) |
| G-5 | JTC-D rebuilt with rolling date-bounded lookback (no leakage) | NOT_MET (pending rebuild) |
| G-6 | Intent coverage >= 80% on 5+ consecutive race days | NOT_MET |
| G-7 | Operator explicit promotion decision | NOT_MET |

No automatic promotion occurs at any gate threshold. Each gate is a necessary condition.
All 7 must be met before promotion is discussed.

---

## 9. JTC-D Status

JTC-D (Jockey-Trainer-Course-Distance profiles) is shadow-only until rebuilt.

- Current files: `data/features/jtc_d/` — all-time cumulative (confirmed leakage)
- Sidecar AUC: 0.8418 — this is a leakage artifact, not a real signal
- Required: rolling 90d / 180d / 365d / lifetime-to-date lookback windows with strict date boundary
- No date column exists in current parquets — rebuild required from raw results history

JTC-D must NOT be used in any scoring model until the rolling rebuild is complete and
validated on a held-out period with no future-win bleed.

---

## 10. Sidecar Feed Artifact

**Path:** `data/new_build/sidecar_feed/new_build_signal_YYYY_MM_DD.jsonl`  
**Latest alias:** `data/new_build/sidecar_feed/new_build_signal_latest.jsonl`

The sidecar feed is the canonical output for New Build signals. It is:
- Written by: `scripts/ops/new_build_sidecar_feed_writer.py --date YYYY-MM-DD --execute`
- Read-only: no side effects on any live system
- Self-describing: each record carries `paper_only`, `old_velo_untouched`, `velo_scoring_allowed` flags
- RPR-clean: `rpr_violation_flag` must be False on all records

---

## 11. Outcome Evaluation Schedule

Run the comparison evaluator after sigma results are available for each race day:

```bash
# After sigma results are written:
python scripts/ops/new_build_old_velo_comparison.py --date YYYY-MM-DD --execute
```

Classification sequence:
1. `OLD_VELO_ABSENT_OUTCOME_PENDING` — no verdict file, no sigma (current state for 2026-05-29+)
2. `OLD_VELO_ABSENT_OUTCOME_EVAL_COMPLETE` — sigma available, no verdict file
3. `OUTCOME_PENDING` — verdict file exists, sigma not yet available
4. `OUTCOME_EVAL_COMPLETE` — both verdict file and sigma available, full comparison run

Accumulate evaluations across 30+ race days before drawing conclusions.

---

## 12. Review Schedule

This policy must be reviewed when:
- G-5 (JTC-D rebuild) is completed
- G-6 (Intent coverage gate) passes for the first time
- n >= 50 closed race evaluations are accumulated
- Any sidecar achieves individual validation (step prior to stacking)

Policy version history:
- V1 (2026-05-29): Initial policy, covers two-lane architecture, sidecar feed, promotion gate

---

*Authorised by: Operator decision 2026-05-29*  
*New Build champion: Challenger_V1 (promoted 2026-05-28)*  
*Old VÉLØ: UNTOUCHED | Shadow VÉLØ: UNTOUCHED | Telegram: OFF | Staking: OFF*
