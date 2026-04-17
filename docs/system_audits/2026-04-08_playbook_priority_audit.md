# System Audit — 2026-04-08 — Playbook Priority Audit

## Files

| Playbook | Path | Lines | Status |
|----------|------|-------|--------|
| G | `app/playbooks/playbook_g_sentient_loopback.py` | 677 | PARTIALLY LIVE |
| E | `app/playbooks/playbook_e_attack_doctrine.py` | 344 | DORMANT |
| F | `app/playbooks/playbook_f_execution_sequencer.py` | 397 | DORMANT |
| Orchestrator | `app/playbooks/playbook_orchestrator.py` | 275 | PARTIALLY WIRED |

## Playbook G — Status: PARTIALLY LIVE

**In live scoring (run_prime_today.py):** AUDIT ONLY — instantiated, get_evolutionary_state() called, but NOT fed into scoring model.

**In close_sigma_loops.py (nightly):** LIVE — observe_race_outcome() called per race during sigma reconciliation. This is where G evolves.

**In Betfair agent:** READ-ONLY — get_evolutionary_state() only.

**State file:** `data/sentient_state.json` + Supabase `SENTIENT_STATE_BACKUP`

**Verdict:** G is EVOLVING at night but that evolution NEVER REACHES live scoring.

## Playbook E — Status: DORMANT

Only wired via PlaybookOrchestrator (app/playbooks/playbook_orchestrator.py). Orchestrator imported by: Betfair execution agent ONLY. NOT imported by src/velo_pipeline.py or src/velo_prime_ensemble.py.

## Playbook F — Status: DORMANT

Same as E — only in PlaybookOrchestrator → Betfair agent. NOT in live scoring path.

## Miss Profile Match

| Miss Class | % of Misses | Relevant Playbook Action |
|---|---|---|
| mid_priced_won | 35.1% | E: NARRATIVE_FRACTURE (+1.8x mid), F: FAVOURITE_LIABILITY (-40-85% fav) |
| market_decoy_followed | 26.9% | E: LAY_THE_STORY, SHADOW_TRACKING |
| outsider_won | 10.9% | E: SHADOW_TRACKING, G: hidden_improver_wins |
| short_fav_won | 8.6% | E: LAY_THE_STORY, HOUSE_REVERSAL |

## Revive / Leave Dead

| Playbook | Verdict | Reason |
|---|---|---|
| G | REVIVE (easy) | Already evolving nightly. One line to wire into live scoring. |
| E | REVIVE (medium) | Perfect for mid_priced_won. Needs oracle_data schema verification first. |
| F | REVIVE (medium) | Depends on E. FAVOURITE_LIABILITY directly addresses mid-price miss. |

## Critical Blocker

oracle_data schema may not exist in current live pipeline. Must verify these fields exist before wiring E/F:
- n_arrative_disruption, mpi, chaos_bloom, integrity_score
- story_anchor, power_anchor, threat_cluster, vetp_patterns

## Next Actions

1. Check if oracle_data fields exist in src/velo_pipeline.py
2. Wire G's state into live scoring (minimum: read sentient_state.json, pass thresholds)
3. Shadow test E's NARRATIVE_FRACTURE against mid_priced_won cases in sigma_audits
4. Re-run close_sigma_loops.py to force G evolution on 558-race archive
