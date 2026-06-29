# SUPABASE REALITY AUDIT — VÉLØ ORACLE PRIME

**Date:** 2026-06-10 · Method: REST GET/HEAD only (count=exact headers, select queries). **READ_ONLY_CONFIRMED = YES.**

```
SUPABASE_CONNECTED        = YES
LATEST_VERDICTS_DATE      = 2026-06-10 (generated_at 04:26 UTC, commit e04647d)
LATEST_SIGMA_DATE         = 2026-06-09 (sigma_audits created_at 23:37 UTC)
LATEST_HORSE_RUNS_DATE    = 2026-06-09 (342 rows — June 9 ingest DID land)
LATEST_RPDC_DATE          = 2026-06-10 (381 rows, built 04:22 UTC, before scoring)
JUNE10_PERSISTENCE_STATUS = PROVEN — 34/34 verdicts, 0 null decision_tier, 0 null git_commit_sha
READ_ONLY_CONFIRMED       = YES (no INSERT/UPDATE/DELETE/RPC issued)
```

## Table census (row counts, 2026-06-10)

| Table | Rows | Freshness |
|---|---|---|
| `velo_verdicts` | 3,390 | CURRENT (June 10) |
| `racing_horse_runs` | 94,915 | CURRENT (June 9 — June 10 races not finished) |
| `runner_release_candidates` | 24,740 | CURRENT (June 10: 381) |
| `sigma_audits` | 2,528 | CURRENT (June 9) |
| `pipeline_runs` | 251 | CURRENT (June 10 PASS, manual trigger) |
| `races` / `runners` | 3,675 / 17,386 | active |
| `learned_patterns` | 344 | not dated here |
| `market_snapshots`, `results` | 0 | EMPTY — never populated |
| `learning_events` | does not exist (PGRST205) | — |

## Field truth on June 10 verdicts

| Question | Answer |
|---|---|
| `decision_tier` written? | YES — 34/34 non-null |
| `git_commit_sha` written? | YES — 34/34 = e04647d |
| `source_truth` written? | **NO — column does not exist on `velo_verdicts`** |
| `feature_degraded` written? | **NO — column does not exist** |
| Ensemble truth written? | YES — `active_components=[sqpe_v17, improvement_score, market_deception_score]`, `excluded_from_ensemble=[place_prob, longshot_score, release_window_score, comment_intel_score]` on every row — live formula proven per-row |
| RPDC tag fields written? | **WRITTEN BUT WRONG — see finding 1** |

## Finding 1 — RPDC columns hijacked since 2026-04-21 (CRITICAL)

- `runner_release_candidates` is healthy: June 10 has 381 rows with real RP IDs, correct race_ids, tags (e.g. horse 7441070 in race 920147: `["PLACE_FORM"]`, score 0.80), built at 04:22 — 3 minutes BEFORE scoring.
- The scoring run attaches them correctly: local backup `data/velo_prime_verdicts_2026_06_10.json` shows `rpdc_lookup_status: "attached"` on **34/34** races with real tags.
- But `app/services/velo_prime_service.py` (~line 933, commit `fda78d4` 2026-04-21 "Deep-wire Racing Post PDF intelligence") **overwrites the RPDC columns in the persist payload**: `rpdc_release_score ← plot_conviction`, `rpdc_primary_tag ← "PDF_PLOT" or null`, `rpdc_tags ← intent_signals`, `rpdc_tag_count ← len(intent_signals)`.
- Result: June 7, 8, 9, 10 verdicts all show `rpdc_tagged = 0` in Supabase. **Every RPDC-based audit reading `velo_verdicts` after 2026-04-21 has been reading PDF-plot data, not RPDC data.**
- Fix (needs operator approval — Supabase write semantics): persist genuine `top["rpdc_*"]` fields; move PDF-plot data to its own columns (`pdf_plot_score`, `intent_signals`).

## Finding 2 — Degradation status not persisted
`source_truth`/`feature_degraded` exist only in local observability JSON. A Supabase consumer cannot tell June 10 (DEGRADED) from June 9 (CLEAN). Requires a migration (operator approval).

## Finding 3 — June 9 ingest actually ran
`racing_horse_runs` has 342 rows for run_date 2026-06-09 — Step 13 completed despite session notes saying steps 13–20 were not run. Steps 14–20 proof files are absent locally, so the rest of the evening chain remains unproven for June 9.

## Persistence gaps summary
```
PERSISTENCE_GAPS =
  1. RPDC columns carry PDF_PLOT semantics since 2026-04-21 (silent severance)
  2. source_truth / feature_degraded not on velo_verdicts
  3. market_snapshots, results tables exist but have never been written
  4. learning_events table referenced in prompts/docs does not exist
```
