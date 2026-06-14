# RPDC — 100-DAY HISTORICAL IMPACT AUDIT

**Date:** 2026-06-10 · Evidence: `data/current/velo_100_day_truth_ledger.json`.

## The critical distinction first
**The picks were not wrong because RPDC persisted wrong.** RPDC is attached as *passive metadata* after scoring computes ranks (`run_prime_today.py` attaches to the already-scored top pick; "RPD-C Engine — does not alter scores or rankings", confirmed in code). What is corrupted is the **evidence label layer**: what RPDC said about each pick, as recorded in Supabase. Strike rates, tiers, and verdicts stand as historical outputs.

RPDC's role per layer:
| Layer | RPDC role | Impact |
|---|---|---|
| Scoring/ranking | none (passive) | **UNAFFECTED** |
| Feature health | not a live-weighted component | UNAFFECTED |
| Learning evidence | rpdc fields feed evidence datasets and audits | **AFFECTED** (labels wrong/absent) |
| Public reporting | RPDC sidecar stats (e.g. "release score >0.5 SR=24.1%") | **AFFECTED — all RPDC sidecar claims after 2026-04-21 are void** |
| Sigma explanation | rpdc tags appear in sigma context | AFFECTED (labels), wins/losses unaffected |

## Dates affected

**Persist hijack (fda78d4, 2026-04-21 → 2026-06-10):** 33 days classified `RPDC_PERSIST_CORRUPTED` + the hijack flag appears on 44 days total. Supabase RPDC tags exist on exactly **2 days in history** (2026-04-13, 2026-04-21); from 2026-04-22 onward the boundary silently erased RPDC evidence daily.

**Attach failure (18 days):** 2026-04-16→25, 2026-04-27→29, 2026-05-02→05, 2026-06-09. On these days candidates existed in `runner_release_candidates` but scoring attached nothing (June 9 root cause: synthetic-ID cards; the April/May cluster predates the current attach instrumentation — same ID-boundary class, including days when the RPDC zero-runner bug documented in THE_ONE_TRUTH was active). **June 9 was not an outlier; attach failure was chronic.**

## Repairability

| Bucket | Days | Repairable? |
|---|---|---|
| Local backup has genuine attached RPDC, Supabase null | June 10 (34 races) — and any other day whose backup carries `rpdc_lookup_status: attached` | **YES** — from local backup, via dry-run repair tool, operator-approved |
| Attach never happened (local has no RPDC data) | the 18 attach-failure days | **NO** for verdict rows (nothing genuine to restore) — but candidates still exist, so *analytical* reconstruction (join candidates to picks by date+name) is possible for research, clearly labelled RECONSTRUCTED, never written to verdict rows |
| Pre-hijack days | Apr 13, Apr 21 morning | Already genuine — leave untouched |
| Cron-era days without local backup (18 days) | — | NO local source of truth; HISTORICAL_OUTPUT_ONLY |

## Was learning affected?
Yes, at the evidence level: 23 shadow learning runs consumed days inside the corrupted window (see LEARNING_100_DAY_CONTAMINATION_AUDIT.md). Live state untouched on all 23 (`live_sentient_state_touched: false` on every status file).

## Recommended repair path (no action without approval)
1. Forward path already fixed (`66d23a0` persist, `122b1de` attach fallback, preflight gate).
2. Historical Supabase repair: dry-run tool over the local-backup-repairable subset only — see HISTORICAL_REPAIR_APPROVAL_PACKET.md item B.
3. RPDC sidecar performance claims: void all RPDC-tag-based statistics computed from `velo_verdicts` for 2026-04-21→2026-06-10; recompute only after repair, or from `runner_release_candidates` joined analytically (labelled RECONSTRUCTED).
4. Attach-failure days: no verdict-row repair; mark permanently `RPDC_ATTACH_FAILURE` in the ledger (done).
