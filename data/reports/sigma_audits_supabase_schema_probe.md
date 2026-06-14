# Sigma Audits — Supabase Schema Probe
## VÉLØ Oracle Prime — Read-Only Archive Intelligence

**Status**: READ_ONLY — no writes, no backfill, no mutation
**Generated**: 2026-06-14
**Classifications**: SIGMA_AUDITS_SCHEMA_PROBE_COMPLETE · VP_EXTRACTION_VERIFIED · NO_SUPABASE_WRITES

---

## Table: `public.sigma_audits`

| Field | Value |
|---|---|
| Total rows | **2,715** (current as of 2026-06-14) |
| Date range | 2026-01-09 – 2026-06-13 |
| Null date rows | 153 |

---

## Schema Columns

```
id, race_id, date, track, outcome, miss_reason, event_type, horse_id,
verdict_id, notes, confidence_level, verdict_score, top_pick_position,
actual_winner_id, actual_winner_sp, decision_tier, off_time,
actual_winner_name, doctrine_event_id, created_at
```

**No top-level `velo_prime_prob` column exists.**

---

## VP Location

VP is in the `notes` field (plain string) as `prob=X.XXXX`:

| Era | Format |
|---|---|
| Mar–Apr | `pred=Horse prob=0.1437 AT BASELINE — ...` |
| May–Jun | `{"summary": "pred=Horse | prob=0.3525 ABOVE BASELINE ..."}` |

**Extraction regex**: `prob=([\d.]+)` — works across both formats.

---

## VP Extraction Results

| Category | Rows | Pct |
|---|---|---|
| VP extractable (prob=) | **2,286** | **85.1%** |
| verdict_score only | 363 | 13.5% |
| Neither | 37 | 1.4% |

---

## Era Split

| Era | Total rows | VP rows | VP coverage |
|---|---|---|---|
| Jan–Feb 2026 | 37 | 0 | 0.0% — skeleton |
| Mar–Apr 2026 | 1,271 | 1,061 | 83.5% — pre-surgery |
| **May–Jun 2026** | **1,225** | **1,225** | **100.0%** |
| NULL date | 153 | 0 | 0.0% — exclude |

---

## Row Count History

| Snapshot | Count | Status |
|---|---|---|
| "2,528" | Stale (early project) | Table has grown |
| "2,686" | Stale (prev session) | Table has grown |
| **2,715** | **Current (2026-06-14)** | **Confirmed via Content-Range** |

---

## Outcome × VP Signal (2,286 VP rows)

| Outcome | Mean VP |
|---|---|
| WIN | **0.3367** |
| PLACED | 0.2948 |
| MISS | 0.2394 |

---

*SIGMA_AUDITS_SCHEMA_PROBE_COMPLETE — Read-only — 2026-06-14*
