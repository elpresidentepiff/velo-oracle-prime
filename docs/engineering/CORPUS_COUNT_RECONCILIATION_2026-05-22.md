# VÉLØ Corpus Count Reconciliation

**Date:** 2026-05-23  
**Purpose:** Explain the three corpus row counts in circulation and designate source-of-truth for each purpose

---

## The Three Counts

| File | Rows | Scope | Purpose | Source |
|---|---|---|---|---|
| `data/velo_innovation_protocol_1k_deduped.csv` | **1,018** | Top-pick per verdict, local files | Router lane tracking, P&L simulation | Local verdict + result files |
| `data/velo_unified_evidence_corpus_v1.csv` | **1,593** | Top-pick per sigma audit, 40 dates | Signal promotion, sidecar audit | Supabase + local, run 2026-05-17 |
| `scripts/data/velo_unified_evidence_corpus_v1.csv` | **0** | Header-only stub | Not a corpus — wrong location | N/A |

---

## What Each File Is

### 1 — Innovation Protocol Corpus (`velo_innovation_protocol_1k_deduped.csv`)

**1,018 rows** as of 2026-05-23. Covers any date where a local `velo_prime_verdicts_*.json` file exists on disk.

Built by: `scripts/ops/build_innovation_protocol.py`

- One row per verdict race (top pick only)
- Joined to local `results_*.json` files for SP and position
- Router shadow lane flags (V1, V2, V6) applied on every row
- P&L simulation per candidate lane
- **Incremental append** — run with `--date YYYY-MM-DD` for each new day

**Source of truth for:** router lane tracking, V1/V2/V6 P&L simulation, candidate_execution_allowed promotion evidence.

**May 20 status:** 0 rows (excluded — SCORING_FLATLINE_CONTAMINATED). May 21 (44 rows) and May 22 (43 rows) added 2026-05-23.

---

### 2 — Unified Evidence Corpus (`data/velo_unified_evidence_corpus_v1.csv`)

**1,593 rows**, date range 2026-03-17 → 2026-05-19. Covers 40 race dates.

Built by: `scripts/audit/build_unified_evidence_corpus.py`

- One row per sigma audit entry (top pick per race)
- Sourced primarily from Supabase `sigma_audits` + local verdict files
- Contains all sidecar signal fields: market_deception_score, improvement_score, place_prob, g_shadow_mode, etc.
- Broader date coverage (40 dates) than the innovation protocol (was 5 dates before today)
- Last run: 2026-05-17 — does not yet include May 21 or May 22

**Source of truth for:** signal promotion audit (VP band, tier, sidecar SR/frame), unified evidence audit reports, signal ranking table. This is what feeds `velo_unified_evidence_audit_v1.json`.

**Note:** This corpus needs a separate rebuild pass to include May 21 and May 22 (see below).

---

### 3 — `scripts/data/velo_unified_evidence_corpus_v1.csv` (0 rows)

Header-only stub. Wrong location. The correct output path for `build_unified_evidence_corpus.py` is `data/velo_unified_evidence_corpus_v1.csv`. This file can be ignored.

---

## Why the Counts Differ

| Dimension | Innovation Protocol | Unified Evidence Corpus |
|---|---|---|
| Row scope | 1 per verdict (top pick) | 1 per sigma_audit row (top pick) |
| Date coverage | Any date with local verdict file | 40 dates via Supabase, 2026-03-17 to 2026-05-19 |
| Data source | Local JSON files | Supabase sigma_audits + local |
| Router lanes | Yes (V1/V2/V6 flags, P&L) | Yes (from innovation protocol join) |
| Sidecar signals | Partial (from verdict top field) | Full (market_deception, improvement, etc.) |
| Requires Supabase | No | Yes |

The counts differ because they have different date ranges and different data sources. They are not competing versions of the same thing — they serve different purposes.

---

## The "1,593 vs 931" Question

The "931" count referred to the innovation protocol **before** the May 21/22 rebuild (now 1,018). The "1,593" is the unified evidence corpus with Supabase-sourced data across 40 dates. They are different corpora with different scopes.

There is no discrepancy to fix. The counts are both correct for their respective scopes.

---

## Unified Evidence Corpus — Update Needed

`data/velo_unified_evidence_corpus_v1.csv` currently ends at 2026-05-19. To include May 21 and May 22:

```bash
source venv/bin/activate && PYTHONPATH=. python scripts/audit/build_unified_evidence_corpus.py
```

This requires Supabase connectivity and will pull sigma_audit rows for May 21 and May 22. May 20 is automatically excluded as it has no sigma_audit rows (flatline — no verdicts produced). Run this after sigma audits for both dates are confirmed complete in Supabase.

---

## Governance

```
Innovation protocol corpus:          data/velo_innovation_protocol_1k_deduped.csv
Unified evidence corpus:             data/velo_unified_evidence_corpus_v1.csv
Contaminated date (do not append):   2026-05-20 (SCORING_FLATLINE_CONTAMINATED)
Both files:                          gitignored (data/ pattern)
No scoring, routing, or model changes arise from corpus counts
```
