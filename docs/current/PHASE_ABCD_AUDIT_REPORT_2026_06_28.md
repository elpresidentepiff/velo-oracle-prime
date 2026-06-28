# VÉLØ Phase A–D Audit Report
**Date:** 2026-06-28 | **Scope:** Signal integrity, sidecar wiring, sigma corpus, evidence scrapers  
**Status:** COMPLETE — all 14 tasks done, 3 operator decisions pending

---

## Summary

Fourteen tasks across Phases A–D completed over two sessions. No live scoring changed. No model weights touched. No Supabase writes. All new code is shadow/evidence/sidecar only. Three operator decisions remain outstanding.

---

## Phase A — Signal Integrity Audit

### A-1 — OR Cross-validation: PASS
- Existing cross-validation logic confirmed correct in the production ensemble.
- No changes required.

### A-2 — Result Reconciliation: RESOLVED
- Supabase `race_results` table confirmed dead (0 rows for current era).
- Local sigma files (`data/sigma_results/`) are the operational truth for result reconciliation.
- May 28 sigma file has `evaluated_count=0` — this date is **irretrievable** (capture failure). Documented gap.

### A-3 — Going Code Scale: BUG FOUND — OPERATOR DECISION PENDING

**Critical mismatch confirmed in both scorer files:**

| File | Line | Current mapping | Training scale |
|---|---|---|---|
| `new_build_velo/paper_scorer.py` | 189 | Heavy=0, Good=3, Firm=5 (0–8) | -1 to 2 (raceform_v17) |
| `scripts/ops/new_build_two_lane_score.py` | 82 | Same 0–8 mapping | -1 to 2 |

`going_code` is feature rank 18 in the champion model. The mismatch means going is scored outside the range the model was trained on — it still fires, but in the wrong zone of the decision boundary.

**Options:**
- **Option A (recommended):** Update both `_going_code()` functions to return values on the -1 to 2 scale matching raceform_v17 training.
- **Option B:** Retrain with the current 0–8 scale as canonical.

**No fix applied — awaiting operator decision.** Fix is one-line in each file when decision is made.

### A-4 — JTC-D Leakage: QUARANTINE CONFIRMED
- Static JTC-D profiles (all-time cumulative): `LEAKAGE_RISK` — correctly excluded from all production scoring paths. Remains quarantined.
- Rolling JTC-D (`jtc_d_rp/`): CLEAN, SHADOW ONLY. Needs separate sidecar validation task before any promotion.
- No JTC-D in champion model feature matrix — confirmed.

---

## Phase B — Sidecar Signal Wiring

### B-1 — BHA OR-diff → RPDC Tag: DONE
**File:** `scripts/ops/run_prime_today.py` (function `_apply_bha_or_diff_to_rpdc()`, line 788; called at line ~1940)

Logic wired (shadow/evidence only — does not affect VP or scoring):
- BHA LOWERED ≥3pts AND horse has `MARK_NEAR` tag → appends `BHA_MARK_CONFIRMED`, adds +0.5 to `rpdc_release_score`
- BHA RAISED ≥3pts AND horse has `MARK_READY` tag → appends `BHA_MARK_RAISED` as suppressor
- Both directions stored in `bha_or_diff_flag` and `bha_or_diff_magnitude` fields on the verdict

### B-2 — BHA Form Momentum: DONE
**File:** `new_build_velo/paper_scorer.py`

Three functions added before `_going_code()`:
- `_load_bha_perf_figures_lookup()` — loads `data/bha_perf_figures_latest.csv`, returns name→[(surf,fig)...] dict. 11,817 horses.
- `_bha_slope()` — linear regression slope over performance figures oldest→newest.
- `_bha_form_momentum()` — returns four fields per horse: `bha_form_momentum` (float slope), `bha_form_latest_fig` (int), `bha_form_n` (count), `bha_form_flag` (one of: NO_DATA, SPARSE, ACCELERATING, PROGRESSIVE, STABLE, REGRESSING, DECLINING).

Wired in `build_paper_predictions()` after `_race_normalize()`. Attaches all four fields to every paper row as sidecar shadow — NOT in champion model feature matrix, NOT in live scoring.

Flag thresholds:
- slope > +2.0 → ACCELERATING
- slope > +0.5 → PROGRESSIVE
- -0.5 ≤ slope ≤ 0.5 → STABLE
- slope < -2.0 → DECLINING
- else → REGRESSING

### B-3 — Macro Context Wiring: AUDIT PASS (already wired)
Traced execution path: `run_prime_today.py` → `score_race_velo_prime()` → `velo_prime_service.py` → `get_macro_context_for_race()` → `ensemble.predict_race(macro_context=ctx)`.

Macro context is fully wired. Outputs already attached to every verdict:
- `macro_chaos_mode`, `macro_regime_label`, `favourite_trap_risk`, `thin_market_uncertainty`
- Year clamped to 2024 for 2026 races (BHA data coverage ends 2024).

No code changes needed.

### B-4 — JTC-D Course Master Wiring: AUDIT PASS (correctly absent)
JTC-D is a runner-level trainer/jockey venue strike-rate signal. Course Master is a venue-level VELO performance overlay. These are different layers — mixing them would be wrong.

JTC-D correctly absent from all production scoring paths. Rolling JTC-D (`jtc_d_rp/`) is shadow-only and awaiting its own sidecar validation task. No wiring needed or made.

---

## Phase C — Sigma Corpus & Threshold Calibration

### C-1 — Local Sigma Corpus Build: DONE
**New file:** `scripts/audit/build_sigma_local_corpus.py`  
**Output:** `data/training/sigma_local_corpus_latest.parquet` + `data/training/sigma_local_corpus_latest.json`

- **Coverage:** 1,050 rows across 36 dates (May 21 – Jun 27)
- **Overall SR:** 26.7% (284 wins)
- **Join key:** `race_id` (sigma outcome files × local verdict JSON)
- **37 sigma files total** — May 28 excluded (evaluated_count=0, irretrievable)
- Fields include: all VP signals, SQPE variants, improvement/MDS/place_prob, RPDC tags + release score, BHA OR-diff, surf_traj, macro flags, confidence level, tier, assigned product

### C-2 — Multi-Model Sigma Analysis: COMPLETE
Key findings from 1,050-row corpus:

| Condition | n | SR |
|---|---|---|
| All rows | 1,050 | 26.7% |
| VP ≥ 0.30 | — | 32.0% |
| VP ≥ 0.40 | — | 37.6% |
| VP ≥ 0.50 | — | 39.1% |
| SQPE + VP both ≥ 0.40 | 155 | 43.9% |
| Confidence HIGH | 97 | 49.5% |
| Confidence LOW | 786 | 23.7% |
| VP ≥ 0.40 + HIGH confidence | 83 | 54.2% |
| Tier A | 288 | 36.5% |
| Tier X | 140 | 16.4% |
| No-RPR max prob | 0.293 | — (never reaches 0.30 gate) |
| G-shadow ON | 1,020/1,050 | not a discriminator |

SQPE standalone shows ~38–39% SR regardless of threshold — expected given it is one of several ensemble components.

### C-3 — RPDC Threshold Calibration: COMPLETE

| Gate | n | SR | Status |
|---|---|---|---|
| RS ≥ 1.5 (release score) | 38 | 44.7% | **KEY GATE — advisory** |
| VP ≥ 0.40 + High confidence | 83 | 54.2% | Best combined gate |
| VP ≥ 0.30 + IMP ≥ 0.4 | 36 | 55.6% | Highest SR (small n) |
| VP ≥ 0.30 + MDS ≥ 0.3 | 53 | 52.8% | Strong |
| VP ≥ 0.30 + SP ≤ 3.0 | 90 | 43.3% | Executability filter |
| VP ≥ 0.40 + Tier A | 250 | 38.0% | Volume gate |
| Base (no filter) | 1,050 | 26.7% | — |

RPDC tag distribution in corpus:
- CYCLE_RUN_1: n=88, SR=31.8%
- CYCLE_RUN_2: n=7, SR=71.4% (very small n)
- PLACE_FORM: n=529, SR=27.2%

**⚠️ WARNING — RPDC Missing Tags:** STABLE_WARM, MARK_READY, MARK_NEAR, and COURSE_RETURN do NOT appear in any May–Jun 2026 sigma corpus row. Only CYCLE_RUN_1/2/3, PLACE_FORM, and WIN_STREAK are present. Root cause not confirmed — may indicate Supabase `runner_release_candidates` table has a gap in tag computation for these classes. **Needs operator investigation.**

---

## Phase D — Evidence Scrapers

### D-1 — BHA GoingStick Scraper: SHELL BUILT
**New file:** `scripts/ops/scrape_bha_going_stick.py`

The BHA going page (`britishhorseracing.com/work-bha/going-extra-furlong/`) is an Angular SPA. Going data is loaded at runtime via a protected API call — not present in static HTML. Even Playwright headless render cannot extract going data (API is authenticated).

Current status: `JS_RENDER_REQUIRED` — scraper shell is complete with static fetch + Playwright fallback, parses table rows and JSON-LD blocks if data ever becomes available in rendered HTML. When BHA makes the data accessible, this scraper is ready.

Output: `data/bha_going_stick_latest.json` + dated snapshot.

### D-2 — Claiming Race OWNERSHIP_CHANGE Badge: DONE
**File:** `scripts/ops/run_prime_today.py` (after `_apply_bha_or_diff_to_rpdc()` call, ~line 1945)

Inline logic — no separate function needed:
```python
_rt = (race.get("type") or race.get("race_type") or "").lower()
if "claim" in _rt:
    _tags = list(top.get("rpdc_tags") or [])
    if "OWNERSHIP_CHANGE" not in _tags:
        _tags.append("OWNERSHIP_CHANGE")
        top["rpdc_tags"] = _tags
        top["claiming_race"] = True
else:
    top["claiming_race"] = False
```
Shadow/evidence only. Does not affect VP, tier, or scoring.

### D-3 — Runner Notes Parser: DONE
**New file:** `scripts/ops/parse_runner_notes.py`

Reads `comment_intel_score`, `nds_narrative`, and `nds_is_fade` from local verdict JSON. Emits NDS_FADE tags via FADE_PATTERNS regex dict (BLED, LAME, UNSEAT, INTERFERENCE, HAMPERED, NEVER_DANGEROUS, LOST_ACTION, FELL, REFUSED, SLOW_START).

Output: `data/runner_notes_YYYY_MM_DD.json`

RP stewards report scraping is NOT yet implemented. Next step is: capture RP result pages → parse `Explanation` / `Stewards` sections → emit additional FADE tags. This is documented as a TODO in the script header.

---

## Open Operator Decisions

| # | Decision | Detail |
|---|---|---|
| 1 | **Going code fix (A-3)** | Option A: update both `_going_code()` in `paper_scorer.py:189` and `new_build_two_lane_score.py:82` to -1→2 training scale. Option B: retrain with 0–8 scale. |
| 2 | **RPDC missing tags** | Why are STABLE_WARM / MARK_READY / MARK_NEAR / COURSE_RETURN absent from all May–Jun 2026 data? Check Supabase `runner_release_candidates` for tag computation gaps. |
| 3 | **RS ≥ 1.5 gate promotion** | RPDC release score gate SR=44.7% at n=38. Advisory now — promote to active signal? |
| 4 | **Rolling JTC-D** | When ready for sidecar promotion (separate validation task required). |

---

## Files Changed This Session

| File | Change |
|---|---|
| `new_build_velo/paper_scorer.py` | B-2: BHA form momentum sidecar added |
| `scripts/ops/run_prime_today.py` | B-1: `_apply_bha_or_diff_to_rpdc()` + D-2: claiming race badge |
| `scripts/audit/build_sigma_local_corpus.py` | New — C-1 corpus builder |
| `scripts/ops/scrape_bha_going_stick.py` | New — D-1 going scraper shell |
| `scripts/ops/parse_runner_notes.py` | New — D-3 runner notes parser |
| `docs/current/PHASE_ABCD_AUDIT_REPORT_2026_06_28.md` | This file |
| `docs/current/ONE_TRUTH.md` | Updated with new scripts and gates |
| `docs/current/VELO_HARDENING_STATE.md` | Updated with A-3 bug, RPDC warning, JTC-D quarantine, D-2 badge |

---

## What Was NOT Changed (Correct)

- No live model weights touched
- No Supabase writes
- No `--promote` used on any retrain
- No Racing API restored
- No scoring formula changed
- Telegram format unchanged
- Going code bug NOT fixed (operator decision required)
