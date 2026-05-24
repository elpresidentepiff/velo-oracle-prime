# Live Scoring Truth Audit — 2026-05-23

**Status:** COMPLETE — runtime code is authoritative  
**Classification:** `LIVE_SCORING_TRUTH_ESTABLISHED` / `DOCS_RECONCILIATION_REQUIRED`  
**Date authored:** 2026-05-23  
**Authority:** El Presidente  
**Profile audited:** `SQPE_IMPROVEMENT_MDS_V1` (active since 2026-05-08, commit `b7e4e0c`)

---

## Purpose

This document resolves the contradiction between `policy_registry_manifest_v1.json`, `CURRENT_RUNTIME_TRUTH.md`, and actual runtime code. The runtime code is the authoritative source. Documents must be corrected to match code — never the reverse.

---

## Method

Inspected in sequence:
1. `src/intelligence/velo_prime_ensemble.py` — `_WEIGHTS`, `_PROFILE_DISABLED`, `_DISABLED_COMPONENTS`, `compute()` method
2. `scripts/ops/run_prime_today.py` — signal usage, tier classification, Telegram dispatch
3. `src/velo/product_router.py` — routing and display
4. `CURRENT_RUNTIME_TRUTH.md` — current documentation state
5. `docs/engineering/policy_registry_manifest_v1.json` — policy claims

---

## Runtime Signal Truth Table

**Profile: SQPE_IMPROVEMENT_MDS_V1 (default)**

| Signal | Calculated? | Displayed? | Used in live VP score? | Used in router/tier? | Used in staking? | Shadow only? | Source file | **Verdict** |
|---|---|---|---|---|---|---|---|---|
| `sqpe_v17_prob` (VP) | YES | YES | **YES — weight 0.45** | YES (primary rank) | NO | NO | `models/sqpe_v17/sqpe_v17.pkl` | **LIVE_WEIGHTED** |
| `improvement_score` | YES | YES | **YES — weight 0.12** | YES (display in signal stack) | NO | NO | `models/specialist/improvement_model/` | **LIVE_WEIGHTED** |
| `market_deception_score` | YES | YES | **YES — weight 0.10** | YES (route gate MDS>0.55) | NO | NO | `models/specialist/market_deception_model/` | **LIVE_WEIGHTED** |
| `velo_prime_prob` (VP output) | YES — output | YES | YES — ensemble output | YES — primary route signal | NO | NO | `src/intelligence/velo_prime_ensemble.py` | **LIVE_WEIGHTED** |
| Macro regime (chaos/fav_trap) | YES | YES (flags) | YES — dampener applied to VP | NO | NO | NO | `src/intelligence/macro_regime/bha_macro_context.py` | **LIVE_WEIGHTED** |
| `place_prob` | YES | YES (badge) | **NO — BADGE_ONLY** (in `_PROFILE_DISABLED` for SQPE_IMPROVEMENT_MDS_V1) | YES (badge display, tier support input) | NO | NO | `models/specialist/place_model/` | **CALCULATED_DISPLAY_ONLY** |
| `longshot_score` | YES | YES | **NO — FROZEN** (in `_PROFILE_DISABLED`, `FREEZE_CANDIDATE` — SP≥10 gate still used in tier X) | YES (tier X trigger: longshot>0.35 AND SP≥10) | NO | NO | `models/specialist/longshot_model/` | **CALCULATED_DISPLAY_ONLY** |
| `release_window_score` | YES | YES | **NO — STORED_ONLY** (weight 0.00, in `_PROFILE_DISABLED` both profiles) | NO | NO | NO | `models/specialist/release_window_model/` | **CALCULATED_DISPLAY_ONLY** |
| `comment_intel_score` | YES | YES | **NO — STORED_ONLY** (weight 0.00, in `_PROFILE_DISABLED` both profiles) | NO | NO | NO | `models/specialist/comment_intelligence_model/` | **CALCULATED_DISPLAY_ONLY** |
| `draw_bias_model` | YES | NO (not in Telegram) | NO | NO | NO | NO | `models/specialist/draw_bias_model/` | **CALCULATED_DISPLAY_ONLY** |
| Playbook G shadow | YES | YES (g_shadow flags in verdict) | **NO — shadow mode** (`VELO_G_SHADOW_MODE=shadow` default) | NO | NO | YES | `src/intelligence/velo_prime_ensemble.py` | **SHADOW_ONLY** |
| `g_shadow_multiplier` | YES | YES (logged) | **NO — not applied to VP in shadow mode** | NO | NO | YES | `src/intelligence/velo_prime_ensemble.py` | **SHADOW_ONLY** |
| Race tier (A/B/C/D/X) | YES | YES | NO — derived classification, not weighted into VP | YES — primary operator signal | NO | NO | `scripts/ops/run_prime_today.py` | **CALCULATED_DISPLAY_ONLY** |
| NO_VP_COMPOSITE shadow | YES (forward gate) | NO | NO | NO | NO | YES | `models/shadow/model_arena_v2/` | **SHADOW_ONLY** |

---

## Active Ensemble Weight Calculation (SQPE_IMPROVEMENT_MDS_V1)

The `compute()` method in `velo_prime_ensemble.py` builds VP as:

```python
total_weight = sum(_WEIGHTS[k] for k in scores)
prob = sum(_WEIGHTS[k] * v for k, v in scores.items()) / total_weight
```

Where `scores` contains only components NOT in `_DISABLED_COMPONENTS`.

Under SQPE_IMPROVEMENT_MDS_V1, `_DISABLED_COMPONENTS` = `{release_window_score, comment_intel_score, place_prob, longshot_score}`.

**Actual active pool:**

| Component | Declared weight | Active under current profile |
|---|---|---|
| sqpe_v17 | 0.45 | YES |
| improvement_score | 0.12 | YES |
| market_deception_score | 0.10 | YES |
| place_prob | 0.08 | NO — BADGE_ONLY (in disabled set) |
| longshot_score | 0.07 | NO — FROZEN (in disabled set) |
| release_window_score | 0.00 | NO — STORED_ONLY (weight 0 AND in disabled set) |
| comment_intel_score | 0.00 | NO — STORED_ONLY (weight 0 AND in disabled set) |

**Effective VP formula (renormalized):**

```
total_active_weight = 0.45 + 0.12 + 0.10 = 0.67
VP = (0.45 × sqpe_v17 + 0.12 × improvement_score + 0.10 × MDS) / 0.67
```

---

## Signal Usage in Telegram and Mission Control

All 7 specialist signals are **calculated and stored** in `velo_verdicts` on every scored race. This means improvement_score, place_prob, release_window_score, and comment_intel_score raw scores appear in Telegram display and Mission Control dashboards regardless of whether they enter the VP calculation.

- **Telegram:** Displays VP, MDS, improvement_score as primary badges. place_prob displayed as badge if >0.80. longshot_score displayed in X-tier diagnostics.
- **Mission Control:** Reads all stored scores from `velo_verdicts`.

Display ≠ weighting. A signal can appear in Telegram without entering VP.

---

## Playbook G Shadow Status

```python
_G_SHADOW_MODE: bool = _os.getenv("VELO_G_SHADOW_MODE", "shadow").lower() != "live"
```

Default: `shadow` (True). The G multiplier is computed on every race and logged in `g_shadow_multiplier` and `g_shadow_flags`, but is **not applied to VP**. VP is unaffected by G in shadow mode.

When promoted to live: set `VELO_G_SHADOW_MODE=live` — this requires El Presidente sign-off.

---

## Contradiction Map

### CURRENT_RUNTIME_TRUTH.md Section 3 — Errors Found

| Signal | Section 3 says | Actual code (SQPE_IMPROVEMENT_MDS_V1) | Correction required |
|---|---|---|---|
| `improvement_score` | declared 0.12, **disabled** — NO | **LIVE_WEIGHTED (0.12)** — NOT in disabled set | Change to LIVE_WEIGHTED |
| `place_prob` | **0.08**, YES live-weighted | **BADGE_ONLY** — in `_PROFILE_DISABLED`, excluded from VP | Change to BADGE_ONLY / CALCULATED_DISPLAY_ONLY |
| `longshot_score` | **0.07**, YES gated | **FROZEN** — in `_PROFILE_DISABLED`, excluded from VP | Change to FROZEN / CALCULATED_DISPLAY_ONLY |
| `release_window_score` | declared 0.10, disabled | STORED_ONLY (weight 0.00, in disabled set) — **CORRECT** | No change needed |
| `comment_intel_score` | declared 0.08, disabled | STORED_ONLY (weight 0.00, in disabled set) — **CORRECT** | No change needed |

**Root cause:** CURRENT_RUNTIME_TRUTH.md Section 3 was never updated after the 2026-05-08 ensemble surgery. It still reflects the LEGACY_FULL_ENSEMBLE profile (pre-surgery) where improvement_score was disabled and place_prob/longshot_score were live-weighted.

### policy_registry_manifest_v1.json SCORING_POLICY_LIVE — Errors Found

| Field | Policy registry says | Actual code | Correction required |
|---|---|---|---|
| `improvement_score` | 0.12 (in weights) | 0.12, LIVE — **CORRECT** | No change |
| `place_prob` | 0.08 (in weights) | BADGE_ONLY — excluded from VP | Remove from live weights, add to badge_only section |
| `comment_intel_score` | 0.08 (in weights) | 0.00 STORED_ONLY — excluded | Remove from live weights, document as STORED_ONLY |
| `release_day_prob` | 0.10 (in weights) | Field does not exist — should be `release_window_score`, weight 0.00 | Fix field name, move to STORED_ONLY |
| `longshot_score` | gated_weights 0.07 | FROZEN — excluded from VP in current profile | Move from gated_weights to FROZEN_NOT_WEIGHTED |
| `arena_v2_status` | "RUNNING — results pending" | **COMPLETE** — all 5 packs GATE_REOPENED | Update to reflect completed results |

---

## Verdict

**CURRENT_RUNTIME_TRUTH.md Section 3 is the wrong document.** It describes the LEGACY_FULL_ENSEMBLE state (pre-surgery), not the live SQPE_IMPROVEMENT_MDS_V1 state.

**policy_registry_manifest_v1.json SCORING_POLICY_LIVE has correct improvement_score** but wrong treatment for place_prob, comment_intel_score, longshot_score, and release_day_prob field name.

**The definitive live scoring truth under SQPE_IMPROVEMENT_MDS_V1:**

```
LIVE_WEIGHTED:
  sqpe_v17_prob        0.45
  improvement_score    0.12
  market_deception_score  0.10

CALCULATED_DISPLAY_ONLY (not VP-weighted):
  place_prob           BADGE_ONLY
  longshot_score       FROZEN (FREEZE_CANDIDATE, ROI=-0.065)
  release_window_score STORED_ONLY
  comment_intel_score  STORED_ONLY

SHADOW_ONLY:
  Playbook G shadow multiplier
  NO_VP_COMPOSITE forward gate model

NO_RUNTIME_IMPACT:
  SQPE v18 (unclassified lab model, not wired)
```

---

```
LIVE_SCORING_TRUTH_AUDIT_STATUS: COMPLETE
ACTIVE_PROFILE: SQPE_IMPROVEMENT_MDS_V1
IMPROVEMENT_SCORE: LIVE_WEIGHTED (0.12) — not disabled
RELEASE_WINDOW_SCORE: STORED_ONLY (weight 0.00) — not live-weighted
COMMENT_INTEL_SCORE: STORED_ONLY (weight 0.00) — not live-weighted
PLACE_PROB: BADGE_ONLY — calculated, displayed, excluded from VP
LONGSHOT_SCORE: FROZEN — calculated, stored, excluded from VP
CURRENT_RUNTIME_TRUTH_MD_SECTION_3: STALE — describes LEGACY_FULL_ENSEMBLE, not current profile
POLICY_REGISTRY_SCORING_POLICY_LIVE: PARTIALLY_WRONG — three fields incorrect
```
