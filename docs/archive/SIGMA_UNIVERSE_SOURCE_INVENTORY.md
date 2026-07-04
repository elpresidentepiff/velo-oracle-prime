# SIGMA UNIVERSE — SOURCE INVENTORY

**Date:** 2026-06-10 · Extractor: `scripts/ops/build_sigma_universe.py` (read-only, rerunnable) · Data: `data/current/sigma_universe.json`.

## The answer to "near 2,000"
**2,528 race-level sigma conclusions** in Supabase `sigma_audits`, one row per (date, race_id), spanning **2026-01-09 → 2026-06-09**. Outcomes: WIN 551 · PLACED 677 · MISS 1,263 · null 37. This is the canonical sigma universe. The previously-quoted "595 sigma-verified picks" was the 19-day local-artifact slice (May 21+) — real, but a subset, exactly as the operator suspected.

## Source map

| Source | Rows | Classification | Verdict |
|---|---|---|---|
| Supabase `sigma_audits` | **2,528** (2,528 unique date+race) | **RACE_SIGMA — CANONICAL** | The universe. 529/551 WIN rows carry winner SP (avg 3.92) → ROI computable |
| `data/sigma_results/*.json` | 19 files (595 evaluated) | DAY_SIGMA | Day summaries derived from race sigma; recomputable window May 21+ |
| `velo_innovation_protocol_1k_deduped.csv` | 1,248 (764 with results) | TOP_PICK_SIGMA / DERIVED | Richest per-pick layer: pick's own SP, model probability, implied probability, edge — the overlay/ROI workhorse |
| `velo_execution_bridge_paper_ledger.csv` | 569 (only ~8 closed) | SHADOW_ROUTER_SIGMA | EVIDENCE_INTEGRITY_SUSPECT — synthetic IDs block result closure |
| `sigma_memory/sigma_retrieval_corpus_v1.jsonl` | 2,528 | DERIVED_DUPLICATE | Exact 1:1 memory copy of the canonical set — confirms dedup |
| `velo_unified_evidence_audit_v1.json` | summary | DERIVED (2026-04-28 snapshot: 49 days, 1,391 rows) | Historical snapshot of the same universe at April 28 |
| `router_shadow_audit_ledger.csv` | aggregates | SHADOW_ROUTER_SIGMA | Lane-level snapshots, not conclusions |
| `scripts/data/velo_unified_evidence_corpus_v1.csv` | **header only — empty** | DERIVED (dead) | Stale placeholder; archive candidate |

## Runner-level sigma
**NOT_FOUND.** Sigma concludes at race level (top pick vs result). No per-runner conclusion universe exists; anything runner-shaped lives in `runner_snapshots` (features, not conclusions).

## Layer rules going forward
- RACE_SIGMA (2,528) is the denominator for any whole-history statement.
- DAY_SIGMA may summarize, never substitute.
- DERIVED layers must cite their parent and may never be added to it (no double counting).
- SHADOW layers are never blended with live-pick layers.
- The truth-ledger day classifications join onto every layer by date — every metric is statable clean/degraded/excluded.
