# VÉLØ — 2k+ Sigma Archive Reconciliation Plan
## Status: PLAN ONLY — no backfill performed

Generated: 2026-06-14

## Summary
- **Corrected row-bearing universe**: 711 rows, May 23–Jun 13 (local files)
- **Canonical 2k archive**: 2,528 rows in Supabase `sigma_audits`, Jan 09–Jun 09
- **Universe gap**: ~1,817 rows older than May 23 exist in Supabase only
- **VP in Supabase sigma_audits**: UNKNOWN — schema inspection required

## Source Inventory

| Source | Classification | Rows | Has VP | Has SP | Has Outcome |
|---|---|---|---|---|---|
| supabase.sigma_audits | CANONICAL_ROW_BEARING | 2528 | UNKNOWN — requires Supabase schema check | UNKNOWN | True |
| local.sigma_results/ | CANONICAL_ROW_BEARING | 711 | True | winner_sp only (race winner, not pick SP) | True |
| local.sigma_memory/sigma_memory_*.jsonl | DERIVED_MEMORY | 388 | PARTIAL — velo_pick_vp present, winner_vp_if_scored present | winner_sp_band (banded, not exact) | miss_type / top_pick_result_position |
| local.sigma_memory/sigma_retrieval_corpus_v1.jsonl | DERIVED_DUPLICATE | 2686 | REQUIRES_CHECK | REQUIRES_CHECK | framed field present |
| local.data/velo_innovation_protocol_1k_deduped.csv | TOP_PICK_SIGMA_DERIVED | 1431 | LIKELY — verdict+result join includes model probs | YES — pick SP included in innovation protocol | YES — result join |
| local.data/nightly_eod_learning_events_*.jsonl | CANONICAL_ROW_BEARING | 919 | True | winner_sp in result_snapshot | True |
| local.data/eod_sigma_study_*.json | LEGACY_UNCLEAR | ? | UNKNOWN | ? | ? |

## Key Reconciliation Risks
1. **Era mismatch**: Jan–Apr rows predate Ensemble Surgery v1 (May 2026). VP not comparable across eras.
2. **VP in Supabase**: Unknown if sigma_audits has velo_prime_prob — must check schema.
3. **Pick SP gap**: sigma_audits likely has no pick SP. Use `velo_innovation_protocol_1k_deduped.csv` for ROI.
4. **Double-counting**: 315 rows overlap between Supabase and local 711-row universe.

## Recommended Next Steps (in order)
1. `SELECT column_name FROM information_schema.columns WHERE table_name='sigma_audits'` via Supabase MCP
2. Sample 5 rows to confirm field names
3. If VP present: count VP coverage by date
4. If VP present and eras manageable: era-flagged export for Jan–May22
5. Join to innovation_protocol for pick SP
6. Operator decision before any merge

**Do not backfill until Supabase schema confirmed and operator approves era-flagged merge.**