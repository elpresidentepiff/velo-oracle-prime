# May 24 — Operator Correction Packet

**Classification:** `2026-05-24_RUN_DEGRADED` / `OFFICIAL_VALID_FEATURE_DEGRADED`  
**Status:** OPERATOR_DECISION_REQUIRED  
**Date:** 2026-05-24  
**Authority:** El Presidente  
**Reference:** `docs/engineering/MAY24_SUPABASE_RPDC_INCIDENT_AUDIT.md`

---

## What Telegram Said

Telegram received and displayed:
- Pre-flight: PASS (7 checks, all green)
- CASH RUNS: 4 horses
- Day posture: `A=1 B=19 C=3 D=0 X=6 [strong card]`
- A-STRIKE (Governed): CUR 1.45 — Sun Goddess — prob=0.3584
- 20 B-PLAYABLE races listed
- C-WATCH list (3 races)
- Place signals
- D/X pass list
- Persistence report: PASS
- Final report: PASS

**No degraded-feature banner was sent. No RPDC warning was sent. No VP formula warning was sent.**

---

## What Was Actually Degraded

### VP formula used in today's Telegram

```
Effective formula:  VP = (0.45 × sqpe_v17 + 0.10 × MDS) / 0.55
Live-truth formula: VP = (0.45 × sqpe_v17 + 0.12 × improvement_score + 0.10 × MDS) / 0.67
```

All VP scores sent to Telegram are approximately **22% higher** than they would be under the full formula. The denominator dropped from 0.67 to 0.55 because improvement_score was excluded.

### CUR 1.45 Sun Goddess — A-STRIKE

```
Sent to Telegram: prob=0.3584 (Tier A)
Full-formula estimate: prob ≈ 0.294 (may still be Tier A — gap was real at 0.1906)
Status: LIKELY VALID but cannot be confirmed without RPDC data
```

The gap (+0.1906) is genuine — it derives from SQPE and MDS, both of which were operational. The A-tier classification was plausibly correct even under the full formula.

### "Strong card" posture

The `[strong card]` label applies to A=1, B=19 on an inflated VP scale. Under the full formula, some B-tier horses may fall to C-tier. The posture should be treated as **VISION_ONLY / INFORMATION_ONLY** for today.

---

## What Was Operationally Degraded

| Component | Status | Impact on Telegram |
|---|---|---|
| SQPE v17 | OPERATIONAL | Normal |
| MDS | OPERATIONAL | Normal |
| improvement_score | EXCLUDED — RPDC zero | VP inflated ~22% |
| RPDC tags | ABSENT — 0/29 races | No release window, cash window, tag context |
| RPDC chain | BROKEN since 2026-05-08 | 16+ days of degraded runs |
| Supabase write | CONFIRMED | Normal |
| Dashboard | LOCAL_JSON fallback | decision_tier NULL |
| decision_tier in DB | NULL — all 29 rows | Cannot filter by tier from DB directly |

---

## Does a Telegram Correction Need to Be Sent?

**Operator decision required.**

Arguments for sending a correction:
- Subscribers saw "strong card" and A-STRIKE without knowing VP was inflated
- The FEATURE_DEGRADED context changes how A/B signals should be weighted
- Transparency principle

Arguments against sending a correction:
- SQPE and MDS both scored correctly — the core signal is real
- CUR 1.45 Sun Goddess had a genuine gap (0.1906) that survives formula correction
- A correction Telegram mid-morning introduces operational noise
- The run is VALID, just feature-degraded

**Recommended operator stance:** Send a brief clarifying note to Telegram if there is active use of the B-tier selections today. For A-tier (CUR 1.45), the signal is likely real. For B-tier horses that passed on VP alone (no MDS, no gap), treat with reduced confidence.

**Do not rescore. Do not resend the full card. Do not overwrite official artifacts.**

If a correction is sent, use this template:

```
⚠ VÉLØ SYSTEM NOTE — 2026-05-24

Today's card was scored with improvement_score excluded (RPDC unavailable — 
engineering issue). Effective formula: SQPE + MDS only (2 of 3 live components).

VP scores are approximately 22% higher than normal.
A-STRIKE CUR 1.45 Sun Goddess — gap signal (0.19) is real.
B-tier horses: treat VP 0.20–0.28 range with reduced conviction today.

Full-formula run requires RPDC chain repair. ETA: after results ingest.

No model change. No router change. Predictions are official.
— El Presidente
```

---

## Is the Dashboard Correct?

The dashboard output (`dashboard_daily_predictions_2026_05_24.json`) was built from local JSON (not Supabase read), using the same 29 VP scores. Content is correct relative to the degraded run. It is not mislabelled — but it does not display a FEATURE_DEGRADED flag.

**Operator decision:** Label or annotate the dashboard file as FALLBACK_LOCAL / FEATURE_DEGRADED if the dashboard is shared externally.

---

## Learning Status

**NO_LEARNING_UNTIL_RECONCILED.**

The following actions are blocked until RPDC chain is repaired and a full-formula run is confirmed:
- `eod_shadow_learning_bridge.py` consumption of 2026-05-24 sigma
- Learning candidate consumption from any day where improvement_score = constant (0.0872)
- Playbook G doctrine update from 2026-05-24
- Any evidence audit that includes the degraded run window

**Degradation scope:** At minimum 2026-05-08 to 2026-05-24. All sigma results in this window used the degraded formula. Before any learning from this window is consumed, the scope must be mapped and operator approval obtained.

---

## Next Safe Commands

**Step 1 — Run yesterday's results ingest (repair horse_runs for 2026-05-23):**
```bash
source venv/bin/activate && PYTHONPATH=. python scripts/ops/ingest_results_to_horse_runs.py --date 2026-05-23
```

**Step 2 — Rebuild RPDC for today (after Step 1):**
```bash
source venv/bin/activate && PYTHONPATH=. python scripts/ops/build_rpdc_daily.py --date 2026-05-24
```
Check that it returns >0 runners.

**Step 3 — Operator decision on re-score:**
After RPDC is rebuilt, operator must decide whether to:
- `RESCORE_TODAY`: rescore all 29 races with full formula, overwrite velo_verdicts, resend Telegram
- `HOLD_AS_DEGRADED`: keep today's official run as OFFICIAL_VALID_FEATURE_DEGRADED, rescore tomorrow clean
- `COMPARE_ONLY`: run a dry comparison (no Supabase write, no Telegram) to quantify the delta

**Step 4 — After results close tonight:**
```bash
# Standard sigma (run regardless of rescore decision)
source venv/bin/activate && PYTHONPATH=. python scripts/ops/run_results_sigma.py --date 2026-05-24

# Results ingest (must run tonight — don't repeat the May 23 miss)
source venv/bin/activate && PYTHONPATH=. python scripts/ops/ingest_results_to_horse_runs.py --date 2026-05-24
```

**Step 5 — Audit degradation scope:**
Check racing_horse_runs and runner_release_candidates gaps back to 2026-05-08 to identify which sigma days are affected.

---

## What Must NOT Happen

```
DO NOT re-run scoring without operator approval
DO NOT resend Telegram with corrected scores without operator approval
DO NOT overwrite velo_prime_verdicts_2026_05_24.json (official local backup)
DO NOT consume 2026-05-24 learning
DO NOT consume any sigma learning from the 2026-05-08 to 2026-05-24 window
DO NOT change model, router, staking, Playbook G, or any live state
```

---

## Classification

```
RUN_ID:                      2026-05-24 velo-prime-scoring
PIPELINE_RUN_ID:             3c4f6b3b-497b-4a67-b785-d86f59cc6a8e
RACES_SCORED:                29/29
SUPABASE_WRITE:              CONFIRMED
PREDICTION_INTEGRITY:        OFFICIAL_VALID_FEATURE_DEGRADED
VP_FORMULA:                  DEGRADED — (0.45×sqpe + 0.10×mds) / 0.55
VP_INFLATION_VS_FULL:        ~22%
A_STRIKE_INTEGRITY:          PLAUSIBLE — gap signal real, tier may hold under full formula
B_TIER_INTEGRITY:            REDUCED — inflated VP, treat with caution
RPDC_STATUS:                 BROKEN — chain has been down since 2026-05-08
LEARNING_STATUS:             NO_LEARNING_UNTIL_RECONCILED
TELEGRAM_CORRECTION_NEEDED:  OPERATOR_DECISION_REQUIRED
NEXT_SAFE_COMMAND:           ingest_results_to_horse_runs.py --date 2026-05-23
NO_SCORING_CHANGE:           CONFIRMED
NO_MODEL_PROMOTION:          CONFIRMED
NO_ROUTER_STAKING_CHANGES:   CONFIRMED
NO_TELEGRAM_RUNTIME_CHANGES: CONFIRMED
NO_PLAYBOOK_G_CHANGES:       CONFIRMED
NO_LIVE_STATE_MUTATION:      CONFIRMED
```
