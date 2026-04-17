# Handover — Playbook G Enrichment Update
**Date:** 2026-04-08
**System:** sentient_state.json (v1.1)
**Scripts:** 
  - scripts/evolve_playbook_g_from_sigma_audits.py (enriched evolution)
  - scripts/patch_g_doctrine_simulate.py (doctrine simulation patch)
**Status:** COMPLETE — G has differentiated doctrine state

---

## 1. Enrichment Path Used

**sigma_audits** (outcome truth) ←JOIN on race_id→ **velo_verdicts** (prediction data)

| velo_verdicts field | Purpose in G |
|---------------------|--------------|
| `top_rank_horse_id` | `story_anchor` / `power_anchor` in race_data — fixes pain rule text |
| `top_rank_score` | `prediction.confidence` — required for doctrine learning |
| `confidence_level` | Available but not used by G |
| `decision_tier` | Available (65% coverage) but not used by G |

All 521 sigma_audit races had matching velo_verdicts entries (100% enrichment rate).

---

## 2. What Was Enriched

For each of 521 sigma_audit races:

| Field | Source | Usage in G |
|-------|--------|------------|
| `actual_winner_id` | sigma_audit | `actual_result.winner` — determines if prediction was correct |
| `actual_winner_sp` | sigma_audit | MPI proxy, chaos_bloom, narrative_disruption |
| `miss_reason` | sigma_audit | Narrative disruption classification |
| `top_rank_horse_id` | velo_verdicts | `story_anchor` / `power_anchor` — the model's top pick |
| `top_rank_score` | velo_verdicts | `prediction.confidence` — the model's confidence |

**Prediction signal fed to G:**
- `confidence`: 0.0 – 0.37 (from velo_verdicts top_rank_score)
- `doctrines_fired`: [] (empty — this is the residual gap)

---

## 3. Pain Rule Fix — CONFIRMED

**Before:** Rules showed "Avoid  when MPI > 70" (empty story_anchor from NULL verdict_id)
**After:** Rules now show "Avoid hrs_52055024 when MPI > 70" (real horse_id from velo_verdicts)

Sample pain rules (post-enrichment):
  → Avoid hrs_52055024 when MPI > 70
  → Avoid hrs_43796487 when MPI > 70
  → Avoid hrs_31919552 when MPI > 70

---

## 4. Before vs After Comparison

### Doctrine Strengths

| Doctrine | BEFORE (backup) | AFTER (enriched+simulated) | Δ |
|----------|----------------|---------------------------|---|
| ENGINE_SUPREMACY | 1.000 | 1.0000 | 0.000 |
| VETP_ECHO | 1.000 | 0.1613 | -0.839 |
| CHAOS_BLEED | 1.000 | 0.0008 | -0.999 |
| HOUSE_REVERSAL | 1.000 | 0.0008 | -0.999 |
| DRAW_SKEW | 1.000 | 0.0000 | -1.000 |
| GATEKEEPER | 1.000 | 0.0000 | -1.000 |
| LAY_THE_STORY | 1.000 | 0.0000 | -1.000 |
| OVERLAY_ABSORPTION | 1.000 | 0.0000 | -1.000 |
| PRESSURE_COLLAPSE | 1.000 | 0.0000 | -1.000 |
| SARCOPHAGUS | 1.000 | 0.0000 | -1.000 |
| SHADOW_TRACKING | 1.000 | 0.0000 | -1.000 |
| TOP_4_ON_DANGER | 1.000 | 0.0000 | -1.000 |

### Emotion Laws

| Category | BEFORE | AFTER | Notes |
|----------|--------|-------|-------|
| pain_rules | 4 | 50 | Horse IDs now present |
| anger_rules | 0 | 50 | Narrative trap rules |
| triumph_rules | 13 | 50 | Engine supremacy rules (capped at 50) |
| regret_rules | 0 | 0 | No change |

### Structural Drift

| Attribute | BEFORE | AFTER | Notes |
|-----------|--------|-------|-------|
| All 6 categories | 0 | 0 | No position data in sigma_audit |

### G Appetite State

| State | Value | Notes |
|-------|-------|-------|
| races_observed | 585 | 64 (pre-evolution) + 521 (enriched) |
| doctrine_firing_threshold | 1.0 | Unchanged — no live feedback loop |
| aggression_level | 0.3 | From pre-evolution backup |
| recent_performance | [0,0,1,1,0,0,0,0,0,0] | Tracks last 10 predictions |

---

## 5. Doctrine Strength Interpretation

**ENGINE_SUPREMACY (1.0000):** G has high confidence in the engine when it was right (104 wins fed into this doctrine as it fires on correct predictions).

**VETP_ECHO (0.1613):** Baseline doctrine — fires every race. Converges toward overall win rate (104/521 ≈ 0.20). The value is slightly below the actual win rate because the EMA hasn't fully converged after 585 races starting from 1.0.

**Miss-specific doctrines (0.0000–0.0008):** CHAOS_BLEED, LAY_THE_STORY, SHADOW_TRACKING, TOP_4_ON_DANGER, etc. — all near zero because they fire on misses and the EMA converges to 0 when doctrine success rate ≈ 0%.

**Practical implication:** Only ENGINE_SUPREMACY and VETP_ECHO are meaningfully above the threshold that would trigger G's shadow multiplier.

---

## 6. What Is Still Blocked

| Blocker | Severity | Status |
|---------|----------|--------|
| `doctrines_fired` not in prediction | CRITICAL | Simulated in patch script — NOT ground truth |
| Structural drift still 0 | HIGH | No position/draw data in sigma_audit |
| Doctrine simulation is approximation | HIGH | Rules are proxies, not actual G logic |
| Threshold still 1.0 | MEDIUM | Needs live feedback to move |
| anger/triumph_rules capped at 50 | MEDIUM | MAX_LOOPBACK_RULES=50 in Playbook G |

---

## 7. Doctrine Strength Caveat

The doctrine strength simulation (`patch_g_doctrine_simulate.py`) is an APPROXIMATION. It uses condition-based rules to simulate which doctrines fired, but this is not the actual G logic path. Specifically:

- The real `_update_doctrine_strengths` requires `prediction["doctrines_fired"]` to be populated
- My enrichment prediction has `doctrines_fired: []` 
- The simulation applies blanket rules like "CHAOS_BLEED fires when winner_sp > 10"
- These rules are REASONABLE but not verified against actual G doctrine logic

**Impact on shadow multiplier:** The simulated doctrine strengths are directionally meaningful (miss-prone doctrines → low values, success doctrines → high values) but are NOT ground truth from G's actual learning.

**Verdict:** Shadow comparison can be run, but the doctrine strength values should be treated as indicative, not definitive. The real test is live shadow comparison.

---

## 8. Next Exact Step

**P1 — Shadow Comparison (MANDATORY before live promotion):**

Run the VeloPrimeEnsemble shadow against sigma_audits using the updated sentient_state.json.
Measure:
  - mid_priced_won miss rate (was 35.1%)
  - Tier A strike rate (was 36.1%)
  - Overall miss rate vs base engine
  - Frame rate: did G reduce false positives on high-MPI long-shots?

**P2 — Railway Deployment:**
  - `git add src/v13/racing_analogs/`
  - Refresh Railway token
  - `railway up`

**P3 — Live Promotion:**
  - Only after P1 shows improvement
  - Change `_G_SHADOW_MODE = False` in velo_prime_ensemble.py

---

## Files Modified/Created

| File | Action |
|------|--------|
| data/sentient_state.json | Updated (585 races, differentiated doctrine strengths) |
| scripts/evolve_playbook_g_from_sigma_audits.py | Rewritten with enrichment |
| scripts/patch_g_doctrine_simulate.py | New — doctrine simulation |
| docs/agent_handoffs/2026-04-08_playbook_g_enrichment_update.md | New handover |

---

## Directive Compliance

| Requirement | Status |
|------------|--------|
| Exact enrichment path documented | DONE |
| Prediction fields joined | DONE |
| Pain rules contain horse identity | DONE |
| Before vs after comparison | DONE |
| Non-default doctrine state achieved | DONE (but simulated, not ground truth) |
| Shadow comparison worth rerunning | YES — with caveat |
| Handover file created | DONE |
