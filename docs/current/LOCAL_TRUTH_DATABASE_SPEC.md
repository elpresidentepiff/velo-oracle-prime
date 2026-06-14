# LOCAL TRUTH DATABASE — SPECIFICATION

**Date:** 2026-06-10 · Engine: **DuckDB** (single file `data/velo_truth.duckdb`; SQLite acceptable fallback). Append-only discipline: corrections are new rows with provenance, never UPDATEs of history.

## Why
Every boundary failure this week — the RPDC hijack, the attach failure, Mission Control's invented CLEAN, the forensic effort of the 100-day ledger — traces to truth living in hundreds of loose JSON files joined by stringly-typed IDs. One queryable store kills the bug class and turns week-long audits into SQL.

## Core law: identity is first-class
The synthetic-vs-real ID failure becomes structurally impossible:

```sql
CREATE TABLE identity_aliases (
  canonical_id   TEXT NOT NULL,      -- real RP numeric id once known
  entity_type    TEXT NOT NULL,      -- race | horse | jockey | trainer | course
  source_id      TEXT NOT NULL,      -- whatever a source called it (incl. rp_VENUE_* synthetics)
  source         TEXT NOT NULL,      -- rp_html | pdf_bypass | racing_api_legacy | manual
  normalized_name TEXT,              -- deterministic name key (rpdc_attach.normalize_horse_name)
  dco_key        TEXT,               -- date|course|off_time composite
  confidence     TEXT NOT NULL,      -- exact | unique_name | operator_confirmed
  first_seen     TIMESTAMP,
  PRIMARY KEY (entity_type, source, source_id)
);
```
Every loader writes its IDs here; every join goes through canonical_id. Ambiguity = no row = loud failure.

## Tables (all append-only, all with `ingested_at` + `source_file` provenance columns)

| Table | Grain | Primary source today |
|---|---|---|
| `race_days` | day | truth ledger / run truth |
| `races` | race | injection JSON |
| `runners` | race×horse | injection JSON |
| `verdicts` | race (top pick) + full per-runner JSON blob | local backups + Supabase mirror |
| `sigma_conclusions` | race | sigma_audits mirror (canonical 2,528) |
| `results` | race×horse | rp_results files |
| `rpdc_candidates` | day×horse | runner_release_candidates mirror |
| `rpdc_attachments` | race (attach method + fields as scored) | scoring run |
| `persistence_proofs` | day | proof artifacts |
| `source_truth_packets` | run | observability packets |
| `feature_health_packets` | run | observability packets |
| `mission_control_status` | day | MC files |
| `learning_admission` | day | gate checker |
| `odds_snapshots` | race×horse×timestamp | **empty until BSP capture lands** |
| `identity_aliases` | entity alias | all loaders |

## Migration path (strangler, not big-bang)
1. **Phase DB-1 (after June 11 clean day):** backfill loader script reads existing artifacts into DuckDB — read-only on sources, no behaviour change anywhere. The 100-day ledger and ROI audit re-implemented as SQL views; outputs diffed against the JSON versions until identical.
2. **Phase DB-2:** loop checkers (`check_loop_health`, `check_rpdc_integrity`, `prove_supabase_persistence`) read from DuckDB first, artifacts as fallback.
3. **Phase DB-3:** daily chain writes to DuckDB *in addition to* JSON artifacts (dual-write, JSON remains the rollback path for a month).
4. **Phase DB-4:** JSON becomes export format; DuckDB is truth. Supabase remains the cloud system-of-record mirror.

## Non-goals
Not a replacement for Supabase (cloud verdicts stay). Not a model feature store (parquet stays for training). No ORM, no server — one file, `duckdb` python package, SQL.

**Approval needed:** none to build Phase DB-1 (read-only backfill); operator approval before DB-3 (dual-write enters the live chain).
