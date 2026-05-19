# Daily Run 2026-05-19 — Pre-Sigma Status

**Status:** ENGINE_COMPLETE_PRE_SIGMA  
**Documented:** 2026-05-19  
**Source:** RP_PROFILE_FALLBACK

---

## Engine Run Summary

| Field | Value |
|---|---|
| Date | 2026-05-19 |
| Source | RP_PROFILE_FALLBACK |
| Racing API | 401 Unauthorized — graceful fallback, no data loss |
| RP runner profile | Built from 35 PDFs, 318 runners, 6 venues |
| Races scored | 38 |
| Persisted to Supabase | 38 / 38 |
| Dashboard published | 38 |
| Telegram | Sent (pre-flight, card, A-strikes, B-playables, place signals) |
| Score errors | 0 |

---

## Card Summary

| Signal | Count |
|---|---|
| Tier A | 4 |
| Tier B | 22 |
| Tier C | 4 |
| Tier X | 8 |
| VP ≥ 0.30 | 13 |
| VP ≥ 0.40 | 10 |
| MDS > 0.50 | 0 |
| SUPPRESS | 20 |
| VISION_ONLY | 26 |
| PASS | 12 |
| Execution authorized | 0 |

**Tier A selections today:**

| Course | Time | Horse | VP | MDS |
|---|---|---|---|---|
| Cork | 7.42 | Carmel'S Phoenix | 0.9230 | 0.3019 |
| Hexham | 7.20 | Milan Milos | 0.3244 | 0.0617 |
| Huntingdon | 8.00 | Ice Jet | 0.5138 | 0.0515 |
| Lingfield | 2.40 | Vidmiyr | 0.5489 | 0.0511 |

---

## Venues Processed

| Venue | Horses | Races | Plot Candidates |
|---|---|---|---|
| Huntingdon | 40 | 6 | 6 |
| Hexham | 61 | 7 | 15 |
| Cork | 100 | 8 | 3 |
| Lingfield | 87 | 8 | 22 |
| Newcastle | 59 | 7 | 11 |
| Nottingham | 58 | 6 | 8 |

---

## Identity Integrity Audit

**Classification:** `IDENTITY_READY_FOR_SIGMA`

| Check | Result |
|---|---|
| Verdicts count | 38 / 38 expected — OK |
| Dashboard count | 38 — OK |
| Source | RP_PROFILE_FALLBACK (inferred from 38 RP_ IDs) — OK |
| Horse IDs | 38 RP_SYNTHETIC_CLEAN, 0 high-risk |
| Blank horse names | 0 |
| Spaces in IDs | 0 |
| Date mismatches | 0 |
| Sigma matchable | 38 / 38 (primary path) |

All RP synthetic IDs are in normalized format (`RP_horsename` — lowercase, alphanumeric only). No spaces. No blank names. No stale dates.

Audit artifacts:
- `data/reports/2026-05-19_prediction_identity_integrity.json`
- `data/reports/2026-05-19_prediction_identity_integrity.md`

---

## Racing API 401 Note

The Racing API returned 401 Unauthorized at scoring time. Per RP Primary Policy (locked 2026-05-18):

```
API 401 = WARN_ONLY when RP profile exists
```

RP runner profile was available (318 rows built from today's PDFs). Fallback was clean. No data loss.

Pipeline used: RP PDFs → `build_rp_runner_profile.py` → `rp_runner_profile_latest.parquet` → `run_prime_today.py` (RP_PROFILE_FALLBACK path).

---

## Sigma Status

**Sigma not yet run.** Today's results are not available.

Sigma will run after results land (evening). The identity audit confirms all 38 races are Sigma-matchable.

**Learning is blocked until:**
1. Results land
2. Sigma runs and closes loops
3. Identity reconciliation passes

---

## Shadow Model Forward Gate

Gate status: **GATE_OPEN_ACCUMULATING**

| Field | Value |
|---|---|
| Forward rows | 246 / 300 |
| Runners remaining | 54 |
| Challenger Brier | 0.16866 |
| SQPE Brier | 0.21401 |
| Delta | −0.04534 |
| Top-decile SR | 45.45% (n=33) |

Today's 38 predictions are **pending** — they will be added to the forward gate count once results are available and Sigma confirms them.

No production promotion. `consumed_live = False`.

---

## OS / Model-Arena Lane Completion Status

| Task | Status | Commit |
|---|---|---|
| Market feature leakage audit | DONE — CLEAN | `14bce56` |
| Shadow model forward gate update | DONE — n=246/300 | `fd34724` |
| Model artifact governance | DONE | `9279c9d` |
| Mission Control shadow gate display | DONE | `f584b66` |
| 2026-05-19 identity integrity audit | DONE — IDENTITY_READY_FOR_SIGMA | (this commit) |
| 300-runner review packet | DEFERRED — gate at 246/300 | — |

---

## Hard Rules Confirmed

- No scoring changes — CONFIRMED
- No model changes — CONFIRMED
- No router/staking changes — CONFIRMED
- No Telegram sent (from OS tasks) — CONFIRMED
- No Playbook G promotion — CONFIRMED
- No live state mutation — CONFIRMED
- No production use — CONFIRMED
- `consumed_live` = False — CONFIRMED
