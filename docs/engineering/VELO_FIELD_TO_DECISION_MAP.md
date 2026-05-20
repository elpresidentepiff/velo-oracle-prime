# VÉLØ Field-to-Decision Map

**Issue:** #73 — VÉLØ Deep Input Audit  
**Last updated:** 2026-05-19  
**Commit verified against:** `947077b58416ef203c7ef99b39fc1f4962c97387`  
**Evidence:** Code trace + runtime timing audit (2026-05-17, 30 races, 261 runners)

---

## Classification Scheme

| Label | Meaning |
|---|---|
| `LIVE_SCORING` | Enters `score_race_velo_prime()` or ensemble — changes `velo_prime_prob` or rank order |
| `TIER_GATE` | Changes `decision_tier` but NOT `velo_prime_prob` |
| `ROUTER_ONLY` | Affects `assigned_product` or `candidate_execution_allowed` only |
| `SHADOW_ONLY` | Written to shadow ledger; no scoring/tiering/routing effect |
| `OPERATOR_ONLY` | Only shown in Telegram or log output |
| `DISPLAY_ONLY` | Stored in Supabase, shown in cards — never read by scorer/router/tierer |
| `STORED_ONLY` | Persisted to `velo_verdicts`; observability only |
| `FEATURE_DICT_ONLY` | Enters `_build_live_features()` feats dict but is not consumed by any model — not in `ALL_V17_FEATURES` or any specialist `metadata.json` features list, and not directly read by tier/router/shadow logic |
| `IGNORED` | Present in raw data; never read |

A field is only classified `LIVE_SCORING` if it can be traced from raw runner data through to a value that changes `velo_prime_prob`, rank order, `decision_tier`, router lane, or shadow ledger output.

> **Doctrine rule:** Entering `_build_live_features()` is **not** sufficient evidence for `LIVE_SCORING`. A field must appear in `ALL_V17_FEATURES` (`model_manager.py:51–92`) **or** a specialist model `metadata.json` `features` list **or** be directly read by a tier/router/shadow function to be classified as consumed. Fields that enter the feats dict but are not in any model's feature list are `FEATURE_DICT_ONLY` at best.

---

## Field Classification Table

### Group A — Racing Post Intelligence Fields

| Field | Classification | Evidence | Mutates | Notes |
|---|---|---|---|---|
| `spotlight` (raw text) | **SHADOW_ONLY** | `run_prime_today.py:1448` — parsed **after** `score_race_velo_prime()` returns | `spotlight_score` badge (0–1, stored) | Timing audit confirmed: raw text never enters `_build_live_features()`. NLP extraction post-scoring. Cannot affect `velo_prime_prob`. |
| `postdata_score` | **STORED_ONLY** | `velo_prime_service.py:182` — enters feats dict; `:344` — stored on runner; `run_prime_today.py:869, 922` — persisted to `velo_verdicts` | none | **Not in `ALL_V17_FEATURES`** (`model_manager.py:51–92`). **Not in any specialist `metadata.json`** (all 7 checked). Enters feats dict but no model reads it. Stored for observability and operator use only. |
| `or_compression_score` | **FEATURE_DICT_ONLY** | `velo_prime_service.py:181` — enters feats dict only | none | **Not in `ALL_V17_FEATURES`**. **Not in any specialist `metadata.json`**. Not stored back on runner (no `runner["or_compression_score"]` assignment). Passed into `route_data` in `run_prime_today.py` but `product_router.py` contains no gate that reads it (confirmed by grep). Consumed nowhere. Cf. `mark_compression_score` below which IS live. |
| `mark_compression_score` | **LIVE_SCORING** | `model_manager.py:78` — in `V17_DOCTRINE_FEATURES` → `ALL_V17_FEATURES`; specialist metadata: improvement_model, market_deception_model, place_model, longshot_model, release_window_model | `velo_prime_prob` via SQPE v17 + 5 specialists | Distinct from `or_compression_score`. Derived from OR trajectory history, not from `pdf_intel`. Confirmed live in model feature vectors. |
| `plot_conviction` | **TIER_GATE** | `run_prime_today.py:406–416` — `_apply_tie_v3_gate()` PLOT_UPGRADE rule | `decision_tier` (upgrade C→B at ≥0.70, B→A at ≥0.85) | Extracted pre-scoring, stored on runner. TIE gate reads it post-scoring to upgrade tier. Does **not** alter `velo_prime_prob`. |
| `is_postdata_pick` | **DISPLAY_ONLY** | `run_prime_today.py:1522` — passed to `route_data` dict | none | Included in `route_verdict()` input but no logic in `product_router.py` gates on it. |
| `is_topspeed_pick` | **DISPLAY_ONLY** | `run_prime_today.py:1523` — passed to `route_data` dict | none | Same as `is_postdata_pick`. Router ignores it. |
| `ts` / top speed | **LIVE_SCORING** | `velo_prime_service.py:73, 105–106` — `ts_raw = _clean_rating(runner.get("ts"))` → `ts_num`, `ts_missing` | `velo_prime_prob` via SQPE v17 | Rating field, normalized relative to field. `ts_missing` flag adds uncertainty signal. SQPE v17 primary input. |
| `official_rating` / `ofr` | **LIVE_SCORING** | `velo_prime_service.py:71, 91–96` — `or_raw = _clean_rating(runner.get("official_rating"))` → `or_num`, `or_vs_field` | `velo_prime_prob` via SQPE v17 | Relative to field (`or_vs_field`). One of SQPE's most important inputs. |
| `rpr` (Racing Post Rating) | **LIVE_SCORING** | `velo_prime_service.py:72, 98–103` — `rpr_raw = _clean_rating(runner.get("rpr"))` → `rpr_num`, `rpr_vs_field` | `velo_prime_prob` via SQPE v17 | Relative to field. Parallel to `or_num`. Both enter SQPE v17 feature space. |
| `last_winning_or` / OR trend | **LIVE_SCORING** | `velo_prime_service.py:138` — `or_mkt_gap`; v17 doctrine features compute OR trajectory from history | `velo_prime_prob` via doctrine features | Implicit in v17 class/OR intent patterns. Not a raw field — derived from trainer-run history. |

### Group B — RPDC Fields

| Field | Classification | Evidence | Mutates | Notes |
|---|---|---|---|---|
| `rpdc_release_score` | **DISPLAY_ONLY** | `run_prime_today.py:1499` — `_attach_rpdc_from_row()` attaches post-scoring | stored on `top` dict | No gate consumes it. Persisted to `velo_verdicts` as observability field. |
| `rpdc_cash_window_flag` | **DISPLAY_ONLY** | `run_prime_today.py:1499` — flag derived from RPDC row | stored on `top` dict | Derived from RPDC tag list. Display badge. |
| `rpdc_tags` / `rpdc_primary_tag` | **DISPLAY_ONLY** | `run_prime_today.py:1477–1480` — RPD-C tagging AFTER scoring | stored on `pred` | RPD-C engine runs post-scoring. Tags not consumed by router/tier. |

### Group C — Specialist/Sidecar Scores

| Field | Classification | Evidence | Mutates | Notes |
|---|---|---|---|---|
| `market_deception_score` | **LIVE_SCORING** | `velo_prime_ensemble.py:347` — 10% weight in `SQPE_IMPROVEMENT_MDS_V1` profile | `velo_prime_prob` (10% weight) | **Highest-lift signal** (n=31, SR=54.8%, Frame=96.8%). Also gates Playbook G pain rules. |
| `improvement_score` | **LIVE_SCORING** | `velo_prime_ensemble.py:343` — 12% weight in active profile; `synthesize_decision()` B-gate reads it | `velo_prime_prob` (12% weight); `decision_tier` (B-gate: `improve >= 0.18`) | ROI: +13.5% post-Ensemble Surgery (n=62, SR=43.5% when >0.40). Second highest-lift signal. |
| `place_prob` | **TIER_GATE** | `velo_prime_ensemble.py:349` — BADGE_ONLY (weight 0.0 in active profile); `synthesize_decision()` A/B/C gates read it | `decision_tier` (A: place≥0.52, B: place≥0.45, C: place≥0.55) | Critical for tiering but excluded from VP calculation. Weight frozen out (BADGE_ONLY). |
| `release_window_score` | **STORED_ONLY** | `velo_prime_ensemble.py:345` — weight 0.0 in all profiles; stored as `release_day_prob` | none | Computed by specialist model, stored, not used in any gate. Observability only. |
| `comment_intel_score` | **STORED_ONLY** | `velo_prime_ensemble.py:351` — weight 0.0 in all profiles | none | Specialist model output, stored, not used. Observability only. |

### Group D — Race and Market Structure

| Field | Classification | Evidence | Mutates | Notes |
|---|---|---|---|---|
| `sp_dec` (SP decimal) | **LIVE_SCORING + TIER_GATE** | `velo_prime_service.py:79–82, 144` — implied probability, log odds; specialist longshot gate; `synthesize_decision()` X-gate | `velo_prime_prob` (via implied prob feature + longshot specialist at SP≥10); `decision_tier` (X: longshot>0.35 + sp_dec≥10) | Central market signal. Conditions the longshot specialist. |
| `field_size` | **LIVE_SCORING + TIER_GATE** | `velo_prime_service.py:118, 157` — `draw_pct`, `draw_size`; `synthesize_decision()` single-runner block | `velo_prime_prob` (positional features); `decision_tier` (field_size==1 forces X) | Both a feature input and a safety gate. |
| `race_class` | **LIVE_SCORING** | `velo_prime_service.py:132` — `class_num = ModelManager._parse_class(race.get("race_class"))` → feature_engineering_v3 class strength | `velo_prime_prob` via SQPE v17 | 0–1 scale. Class delta vs field a v17 doctrine feature. |
| `going` | **LIVE_SCORING + TIER_GATE** | `velo_prime_service.py:131` — `going_code`; `product_router.py:155` DX_GOING_BLOCK | `velo_prime_prob` via SQPE; `assigned_product` (router D/X blocks Good/Firm/Hard) | Going code into SQPE. Router also hard-blocks certain goings for D/X verdicts. |
| `favourite_trap_risk` | **TIER_GATE** | `velo_prime_ensemble.py:380–382` — `prob -= 0.05` when trap=high + is_fav; `synthesize_decision():489` — trap!="high" required for A | `velo_prime_prob` (macro penalty when trap=high + is_fav); `decision_tier` (blocks A-tier) | Macro regime signal from BHA context. Logged in `verdict_flags`. |
| `prob_gap` (VP top − VP second) | **TIER_GATE** | `synthesize_decision():490, 547, 556, 558, 570` — A: gap≥0.08, B: gap≥0.03, C: gap≥0.02 | `decision_tier` (primary determinant) | Computed from ranked runner probabilities. Central to all tier decisions. |
| `velo_prime_prob` | **LIVE_SCORING (output)** | `velo_prime_ensemble.py:392` — weighted ensemble result; `predict_race()` normalizes and ranks | `decision_tier` (gated everywhere); rank order; router input | Final ensemble probability. Produced here. Consumed by everything downstream. |

### Group E — Training and Jockey Signals

| Field | Classification | Evidence | Mutates | Notes |
|---|---|---|---|---|
| `trainer_timing_score` / trainer intent | **TIER_GATE** | `velo_prime_service.py:410–414`; `tie_v3_gate.py:216–218` (MIN_TRAINER_TIMING=0.5); v17 doctrine extractor | `decision_tier` (TIE v3 upgrade path — one of 7+ intent signals; requires ≥3 for upgrade) | Computed from historical trainer-run patterns. TIE v3 gate only — not ensemble weight. |
| `course/distance flags` | **LIVE_SCORING** | `velo_prime_service.py` — `course_distance_win_rate`, `course_win_rate`; v17 doctrine extractor | `velo_prime_prob` via SQPE / doctrine features | Trainer-jockey course+distance win rates. Doctrine signal from 1.7M row history. |

---

## Execution Timeline (confirmed by timing audit + code trace)

```
run_prime_today.py — per-race loop

  1. runner["pdf_intel"] attached to normalized runners
     ↳ plot_conviction → TIER_GATE (TIE v3 reads it post-scoring)
     ↳ is_postdata_pick, is_topspeed_pick → DISPLAY_ONLY (router ignores)
     ↳ postdata_score → STORED_ONLY (enters feats dict, stored on runner, no model reads it)
     ↳ or_compression_score → FEATURE_DICT_ONLY (enters feats dict, not stored, no model reads it)

  2. score_race_velo_prime(race) called
     ↳ _build_live_features() extracts:
       - official_rating, rpr, ts, sp_dec, race_class, going, field_size → LIVE_SCORING (in ALL_V17_FEATURES)
       - mark_compression_score → LIVE_SCORING (in ALL_V17_FEATURES + 5 specialist models)
       - postdata_score, or_compression_score → enter feats dict ONLY — NOT in ALL_V17_FEATURES, NOT in any specialist metadata → not consumed
     ↳ predict_sqpe(features={}, runner, race) — SQPE builds its own feature vector from runner/race directly; feats dict is NOT passed to SQPE
     ↳ VeloPrimeEnsemble.predict_race() computes velo_prime_prob:
       - sqpe_v17 (0.45) + improvement_score (0.12) + market_deception_score (0.10)
       - place_prob, release_window_score, comment_intel_score: BADGE_ONLY / 0.0 weight
     ↳ Returns: predictions ranked by velo_prime_prob

  3. synthesize_decision() applies tier gates:
     - prob_gap gates (A: ≥0.08, B: ≥0.03, C: ≥0.02)
     - place_prob gates (A: ≥0.52, B: ≥0.45, C: ≥0.55)
     - improvement_score B-gate (≥0.18)
     - favourite_trap_risk A-block
     - X-chaos rules (sp_dec≥10 + longshot>0.35, gap<0.015 + place<0.40, etc.)

  4. _apply_tie_v3_gate() applies conviction upgrades:
     - plot_conviction PLOT_UPGRADE (≥0.70 or ≥0.85)
     - trainer/jockey intent signals (≥3 of 7+ for tier upgrade)

  5. route_verdict() assigns product:
     - Reads: tier, conf, sp_dec, prob_gap, mds, track, going, field_size,
              race_type, is_handicap, fav_sp, velo_prime_prob, archetype
     - Ignores: plot_conviction, or_compression_score, is_postdata_pick, is_topspeed_pick

  6. AFTER score_race_velo_prime() returns:
     - Spotlight parsed → spotlight_score (0-1) → SHADOW_ONLY
     - RPD-C tagging → rpd_tag, rpd_confidence → DISPLAY_ONLY
     - RPDC lookup → rpdc_tags, rpdc_release_score → DISPLAY_ONLY
     - Shadow enrichment → racing_api_*_shadow_score → SHADOW_ONLY
     - Shadow ledger append → forward_ledger.csv → SHADOW_ONLY
```

---

## Specialist Ensemble Profile (Active: SQPE_IMPROVEMENT_MDS_V1, since 2026-05-08)

| Score | Weight | Status | Evidence |
|---|---|---|---|
| `sqpe_v17` | 0.45 | **LIVE** | Always active, both profiles |
| `improvement_score` | 0.12 | **LIVE** | +13.5% ROI post-Surgery |
| `market_deception_score` | 0.10 | **LIVE** | Highest-lift signal (SR=54.8% at >0.5) |
| `place_prob` | 0.08 | BADGE_ONLY | Gates tiers but excluded from VP |
| `longshot_score` | 0.07 | FROZEN | Excluded (FREEZE_CANDIDATE) |
| `release_window_score` | 0.00 | STORED_ONLY | Both profiles |
| `comment_intel_score` | 0.00 | STORED_ONLY | Both profiles |

Rollback: `VELO_ENSEMBLE_PROFILE=LEGACY_FULL_ENSEMBLE`

---

## P0 Mismatches

### 1. Spotlight — SHADOW_ONLY (not live as some docs imply)

`docs/VELO_SPOTLIGHT_HARD_LIMITS.md` states Spotlight cannot override structural verdicts. **Confirmed and strengthened:** Spotlight is parsed entirely after scoring. The `spotlight_score` badge (0–1) is stored on `pred` but consumed nowhere in the scoring, tiering, or routing chain. It is observability metadata only.

**Impact on Mid-Price Hunter:** Spotlight text could theoretically carry intent signals (trainer comments, freshness flags) — but currently these are never read by the ensemble or tier gates.

### 2. `is_postdata_pick` / `is_topspeed_pick` — passed to router, never read

Both are included in `route_data` dict passed to `route_verdict()` (lines 1522–1523) but `product_router.py` does not gate on them. They reach the router call but are ignored by the routing logic. This is a dead code path.

### 3. `rpdc_release_score` — named like a scoring field, behaves as display

Field name implies release-window scoring signal. Actually derived from `plot_conviction` after scoring completes. No gate reads it.

---

## Mid-Price Hunter Readiness (SP 3.0–8.5 zone)

SP 3.0–8.5 = 58% of all misses (352/606 cases, 49-day audit).

| Signal | Current classification | Mid-Price Hunter relevance |
|---|---|---|
| `market_deception_score` | LIVE_SCORING (10% weight) | YES — SR=54.8% when MDS>0.5; market decoy signal identifies mid-priced false favourites |
| `improvement_score` | LIVE_SCORING (12% weight) | YES — SR=43.5% at >0.40; improvement in mid-price zone is highest-value target |
| `spotlight_score` | SHADOW_ONLY (0% weight) | **NOT YET** — parsed post-scoring; would need to be moved or a pre-score flag extracted |
| `is_postdata_pick` | DISPLAY_ONLY | **NOT YET** — wired to router but ignored; could gate a mid-price lane |
| `plot_conviction` | TIER_GATE (upgrades only) | PARTIAL — upgrades C→B/B→A; could add mid-price weight condition |
| `or_compression_score` | FEATURE_DICT_ONLY | **NOT YET** — enters feats dict but no model reads it; not in `ALL_V17_FEATURES` or any specialist metadata. Potential future signal but currently unconsumed |
| `place_prob` | TIER_GATE (BADGE_ONLY) | YES — place ROI in MDS+VP30 zone = +73%; could be SP-gated condition |

**Conclusion:** The signals needed for Mid-Price Hunter exist and most are already in the scoring path. The gap is that ensemble weights are **SP-agnostic**. A future mid-price lane would need SP-conditional weighting or a dedicated SP-zone specialist. No code changes in this audit — classification only.

---

## Summary Table (all 27 fields)

| # | Field | Classification |
|---|---|---|
| 1 | spotlight | SHADOW_ONLY |
| 2 | postdata_score | STORED_ONLY |
| 3 | or_compression_score | FEATURE_DICT_ONLY |
| 4 | plot_conviction | TIER_GATE |
| 5 | is_postdata_pick | DISPLAY_ONLY |
| 6 | is_topspeed_pick | DISPLAY_ONLY |
| 7 | ts / top_speed | LIVE_SCORING |
| 8 | official_rating / ofr | LIVE_SCORING |
| 9 | rpr | LIVE_SCORING |
| 10 | last_winning_or / OR trend | LIVE_SCORING |
| 11 | rpdc_release_score | DISPLAY_ONLY |
| 12 | rpdc_cash_window_flag | DISPLAY_ONLY |
| 13 | rpdc_tags / rpdc_primary_tag | DISPLAY_ONLY |
| 14 | market_deception_score | LIVE_SCORING |
| 15 | improvement_score | LIVE_SCORING |
| 16 | place_prob | TIER_GATE |
| 17 | release_window_score | STORED_ONLY |
| 18 | comment_intel_score | STORED_ONLY |
| 19 | sp_dec | LIVE_SCORING + TIER_GATE |
| 20 | field_size | LIVE_SCORING + TIER_GATE |
| 21 | race_class | LIVE_SCORING |
| 22 | going | LIVE_SCORING + TIER_GATE |
| 23 | favourite_trap_risk | TIER_GATE |
| 24 | prob_gap | TIER_GATE |
| 25 | velo_prime_prob | LIVE_SCORING (output) |
| 26 | trainer_timing_score | TIER_GATE |
| 27 | mark_compression_score | LIVE_SCORING |
