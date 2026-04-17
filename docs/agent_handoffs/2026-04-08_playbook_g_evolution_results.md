# Handover — Playbook G Evolution Pass Results
**Date:** 2026-04-08
**System:** sentient_state.json
**Script:** scripts/evolve_playbook_g_from_sigma_audits.py
**Status:** EVOLUTION RUN — COMPLETE WITH DATA GAP

---

## What happened

1. Ran `evolve_playbook_g_from_sigma_audits.py` across all 29 sigma_audit dates
2. Filtered to 17 dates with real winner data (521 races)
3. Fed 477 races to G (Supabase backup confirmed state saved)
4. All 29 dates now have dedup markers in `learned_patterns`

---

## State Before vs After

| Attribute | Before | After | Change |
|-----------|--------|-------|--------|
| Races observed | 64 | 477 | +413 |
| Doctrine strengths | ALL 1.0 | ALL STILL 1.0 | NO CHANGE |
| Pain rules | 4 | 50 | +46 (learning working) |
| Structural drift | ALL 0 | ALL STILL 0 | NO CHANGE |
| Appetite threshold | 1.0 | 1.0 | NO CHANGE |

---

## What worked

Pain rules grew from 4 to 50. G is processing races and learning from MPI patterns.
State persisted to disk correctly via Supabase backup layer.

---

## Why doctrine strengths didn't move

sigma_audit rows have `verdict_score = NULL` for all historical races.

The backfill populated OUTCOMES (who won) but NOT the model's pre-race PREDICTION (what it predicted).

Without `verdict_score`, G's `prediction.confidence = 0` for every race.
Doctrine learning requires `confidence > 0` to evaluate doctrine performance.
Result: G sees 477 races but all with confidence=0 → no doctrine updates.

---

## Why structural drift didn't move

sigma_audit doesn't have draw/position data for winners.
G has no positional signal to learn from.

---

## Pain rules — specific bug

Pain rules are being created with text "Avoid  when MPI > 70" (no horse_id).
The rule text generator in G's `observe_race_outcome` is not including the winner's horse_id.

This is a G learning bug — the rules are technically created but are not actionable
because they don't specify which horse to avoid.

---

## What G's shadow can do RIGHT NOW

With current state (all doctrine strengths = 1.0, all structural drift = 0):

1. **Horse-specific pain rules** (50 rules): Would suppress specific horses by 0.85x
   if current MDS > 0.6 AND horse_id matches. But rules are generic (no horse_id in text).
   Practical impact: NEAR ZERO.

2. **Doctrine discounts**: NOT ACTIVE. All strengths = 1.0 (threshold is strength < 0.5).

3. **Favourite liability**: NOT ACTIVE. Requires doctrine strength < 0.5.

4. **Structural drift adjustments**: NOT ACTIVE. All zero.

---

## What G's shadow CANNOT do yet

- Doctrine discounts (LAY_THE_STORY, SHADOW_TRACKING, NARRATIVE_FRACTURE)
- Structural drift adjustments
- Favourite liability doctrine
- Any meaningful differentiation based on current state

---

## Root cause

The evolution DID work (pain rules grew, state persisted).
But the DATA FEED is incomplete:

  sigma_audit has: outcome, winner_id, winner SP, miss_reason
  sigma_audit MISSING: verdict_score, verdict_id, top_rank_horse_id

G learned from the SP/win data (pain rules grew).
G CANNOT learn doctrines because it doesn't know what the model predicted.

---

## Next exact step

P1: Enrich G's data feed by joining sigma_audits with velo_verdicts
    to get `top_rank_horse_id` and `top_rank_score` for each race.

    Query: SELECT race_id, top_rank_horse_id, top_rank_score, top_rank_position
           FROM velo_verdicts
           WHERE race_id IN (SELECT race_id FROM sigma_audits WHERE winner_id IS NOT NULL)

    Then feed these as `prediction` to G's observe_race_outcome().

P2: After enrichment, re-run evolve_playbook_g_from_sigma_audits.py (with dedup cleared)
    to re-evolve G with the corrected prediction data.

P3: Then check doctrine_strengths — should start differentiating below 1.0.

P4: Only after doctrine strengths move, check if G improves:
    - mid_priced_won miss rate
    - Tier A strike rate stability
    - Shadow comparison vs base engine

---

## Files modified

- data/sentient_state.json (updated from backup to evolved state)
- scripts/evolve_playbook_g_from_sigma_audits.py (new script created)

## Files written

- docs/agent_handoffs/2026-04-08_playbook_g_evolution_results.md
