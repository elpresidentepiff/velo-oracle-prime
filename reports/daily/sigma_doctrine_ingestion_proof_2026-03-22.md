# Phase 1 — Sigma → Doctrine Ingestion Proof
## Date: 2026-03-22

---

## What was built

### A. `_feed_playbook_g()` in `scripts/close_sigma_loops.py`

New function at line ~852. Called as **Step 9** in `main()` after Step 8 (governance proposals).

**Inputs:** `db`, `run_reviews` (in-memory list built during reconciliation), `verdicts_by_race` (dict keyed by race_id), `target_date`

**Per-race mutation:**
- Constructs `race_data` stub, `prediction` dict, `actual_result` from sigma review data
- Calls `SentientLoopbackEngine.observe_race_outcome(race_data, prediction, actual_result)`
- Updates: `doctrine_strengths` (EMA), `emotion_laws` (pain/triumph/anger rules), `appetite_state` (aggression level, thresholds)

**Outputs written:**
- `data/sentient_state.json` — updated doctrine state (local)
- `data/sentient_state_backup_{date}.json` — dated local backup
- `learned_patterns` Supabase row: `SENTIENT_STATE_BACKUP` (cloud backup of full state)
- `learned_patterns` Supabase row: `playbook_g_fed_{target_date}` (dedup marker)

### B. `scripts/feed_sigma_loop.py` (rewritten v2)

Standalone script. VOX calls this after sigma debrief is confirmed in Supabase.

- Reads `races` → `velo_verdicts` → `velo_post_race_reviews` from Supabase
- Reconstructs `run_reviews` + `verdicts_by_race`
- Calls `_feed_playbook_g()` (shared implementation from `close_sigma_loops.py`)
- Returns structured JSON summary

---

## Ingestion path

```
close_sigma_loops.main()
  Step 4 → generate_review() per race
  Step 6 → _update_learned_patterns()
  Step 8 → _create_sigma_proposals()
  Step 9 → _feed_playbook_g()           ← NEW
              │
              ├── SentientLoopbackEngine.observe_race_outcome()  (per race)
              │       ├── _update_behaviour_echo_chamber()
              │       ├── _update_structural_drift_engine()
              │       ├── _update_manipulation_memory_core()
              │       ├── _update_emotion_engine()
              │       ├── _update_appetite_multiplier()
              │       └── _update_doctrine_strengths()    ← EMA update per doctrine
              │
              ├── SentientLoopbackEngine._save_state()
              │       ├── data/sentient_state.json          ← local write
              │       ├── data/sentient_state_backup_*.json ← dated backup
              │       └── learned_patterns:SENTIENT_STATE_BACKUP ← Supabase
              │
              └── learned_patterns: playbook_g_fed_{date}  ← dedup marker
```

---

## Proof: one sigma debrief → one doctrine mutation chain

1. `close_sigma_loops.py` finishes reconciliation for date X
2. `run_reviews` contains N race outcomes (WIN/PLACED/MISS)
3. `_feed_playbook_g(db, run_reviews, verdict_by_race, X)` fires
4. For each race: `observe_race_outcome()` updates `doctrine_strengths` via EMA (0.9 × current + 0.1 × correct)
5. `_save_state()` writes `sentient_state.json`
6. Next prediction call: `SentientLoopbackEngine._get_recent_doctrine_adjustments()` returns updated strengths
7. These flow into `VeloPrimeEnsemble` / `playbook_g` at prediction time

---

## Proof: playbook_g reads new state at prediction time

`_get_recent_doctrine_adjustments()` reads `self.state["doctrine_strengths"]` — the in-memory dict loaded from `sentient_state.json` on engine init.

On Railway: `sentient_state.json` is on ephemeral disk. Supabase backup (`SENTIENT_STATE_BACKUP`) survives restarts — engine loads from disk, falling back to Supabase row if disk missing.

---

## Proof: dedup (duplicate re-run does not double-write)

Dedup check at top of `_feed_playbook_g()`:
```python
existing = db.table("learned_patterns").select("id").eq("pattern_name", dedup_name).execute()
if existing.data:
    log.info("Step 9: playbook_g already fed for %s — skipping", target_date)
    return 0
```

- `dedup_name = f"playbook_g_fed_{target_date}"` — one per date, globally unique
- Second run for same date hits this guard, returns 0, writes nothing
- Verified via code path: `_feed_playbook_g` returns early before any `observe_race_outcome()` call

---

## Required mutation record fields (per dedup marker in learned_patterns)

| Field | Value |
|---|---|
| `source_date` | target_date |
| `source_hash` | SHA256(f"playbook_g:{date}:{fed}")[:16] |
| `doctrine_family` | SENTIENT_LOOPBACK |
| `mutation_type` | observe_race_outcome |
| `sigma_report` | pipeline_runs/{target_date} |
| `fed_count` | N races ingested |
| `wins_fed` | N wins |

All stored in `conditions` JSONB column of the dedup `learned_patterns` row.
