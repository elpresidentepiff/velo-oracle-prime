# NEXUS Targeted Audit — Final Consolidated Findings
**2026-03-24 | velo-oracle-prime | 5 targeted queries**

---

## 1. Topline Verdict

**ONE live production defect:**
> BHA macro parquet is missing on Railway. `data/bha_macro_features.parquet` does not exist in production. The scoring service starts, runs, and produces verdicts — but it runs **underpowered** in regime-sensitive races.

**Severity: MEDIUM-HIGH**

| | |
|---|---|
| **Root cause** | `FileNotFoundError` raised at `bha_macro_context.py:117` — `_load_macro_df()` finds no parquet |
| **What happens** | `velo_prime_service.py:208–214` catches it with bare `except Exception`, sets `macro_ctx = None` |
| **Operational effect** | Chaos mode damping, favourite-trap penalty, and thin-market spread adjustments are silently skipped |
| **Scoring still runs?** | YES — specialist scores produce `velo_prime_prob` without regime corrections |
| **What breaks** | `verdict_flags` and `regime_override` fields are never written. Scores lack regime sensitivity in AW races, low-grade handicaps, and short-field races |
| **What does NOT break** | Core scoring pipeline, sigma close loop, learning patterns, pipeline_runs logging |

**This is a clean issue. One fix. One verification path. No fog.**

---

## 2. Findings Table

| # | Query | Code Truth | Deployment Truth | Live Operational Impact? |
|---|---|---|---|---|
| Q1 | BHA macro failure path | `FileNotFoundError` at `bha_macro_context.py:117` | Parquet absent on Railway | **YES — regime corrections silently skipped** |
| Q2 | Macro consumers + materiality | 3 regime adjustments in `velo_prime_ensemble.py:83–104` | All 3 silently skipped when `macro_ctx=None` | **YES — affects `velo_prime_prob` in chaos/favourite-trap/thin races** |
| Q3 | Playbook G live-read truth | G instantiated at `run_prime_today.py:462` for audit only | Never feeds into scoring model | **NO — learning path only** |
| Q4 | `miss_category` / `miss_evidence` readers | Zero readers in codebase | Staged schema only | **NO — ghost fields, future infrastructure** |
| Q5 | Writer persistence | `write()` tool works correctly | NEXUS spent context on investigation before writing | **NO — audit process issue, not storage** |

---

## 3. Code Truth vs Deployment Truth vs Database Truth

| Domain | State |
|---|---|
| **Code truth** | `bha_macro_features.parquet` generation script exists at `scripts/cache_bha_macro_features.py` |
| **Code truth** | `miss_category` / `miss_evidence` schema added, zero downstream readers |
| **Code truth** | Playbook G dynamic threshold in `playbook_g.py` affects learning, not scoring |
| **Deployment truth** | Railway `data/` directory does not contain `bha_macro_features.parquet` |
| **Deployment truth** | `velo-prime-scoring` runs without the parquet — no crash, silent degradation |
| **Database truth** | `velo_verdicts` are writing successfully — `verdict_flags` and `regime_override` are null |
| **Database truth** | `sigma_audits` writing correctly after `100a56a` fix |
| **Database truth** | `learned_patterns` accumulating normally — 20+ active patterns |

**These are three separate stories. Code truth ≠ deployment truth ≠ database truth. Only the deployment failure matters operationally.**

---

## 4. What Does NOT Need to Be Treated as a Live Production Emergency

| Finding | Why it's not live |
|---|---|
| Playbook G dynamic threshold edits | Learning path only. Affects `observe_race_outcome()` in sigma close — not today's verdicts. Clean separation, no contamination. |
| `miss_category` / `miss_evidence` | Staged schema. Zero downstream readers. Future infrastructure, not current intelligence. |
| Writer persistence | Tool works fine. NEXUS ran out of context doing investigation before writing. Audit process fix only. |
| `SENTIENT_STATE_BACKUP` | Written nightly, read as G fallback. Not read by scoring path. |

---

## 5. Immediate Operator Actions

**In this order:**

**1. Deploy BHA macro parquet to Railway**
```
python scripts/cache_bha_macro_features.py
```
Then upload `data/bha_macro_features.parquet` to Railway `data/` directory for the `velo-prime-scoring` service.

**2. Verify macro file path exists in production**
Confirm `data/bha_macro_features.parquet` is present in the Railway deployment for `velo-prime-scoring`.

**3. Run one fresh scoring cycle**
Trigger a manual scoring run or wait for the 06:00 UTC cron to fire. Check `pipeline_runs` for a clean `completed` entry with `macro_ctx` populated.

**4. Confirm macro flags reappear in verdict output**
Query `velo_verdicts` for a recent race. Verify `full_analysis` JSONB contains `verdict_flags` and `regime_override` fields — these should no longer be null.

**5. Confirm regime-sensitive adjustments are active again**
Check that chaos races (AW, low-grade handicaps, short fields) now show regime annotations in `verdict_flags`. These should appear for the first time in production.

---

## 6. Verification Queries

**Prove macro features present:**
```sql
-- Check that regime_override is no longer null in recent verdicts
SELECT race_id, course, generated_at, confidence_level,
       (full_analysis->>'verdict_flags') IS NOT NULL AS has_verdict_flags,
       (full_analysis->>'regime_override') IS NOT NULL AS has_regime
FROM velo_verdicts
WHERE generated_at > NOW() - INTERVAL '6 hours'
ORDER BY generated_at DESC
LIMIT 10;
```

**Prove verdict flags / regime fields are back:**
```sql
-- Check specific regime fields in full_analysis
SELECT race_id,
       full_analysis->'verdict_flags'->>'chaos_mode' AS chaos_flag,
       full_analysis->'verdict_flags'->>'favourite_trap' AS fav_trap_flag,
       full_analysis->'regime_override' AS regime
FROM velo_verdicts
WHERE full_analysis->>'verdict_flags' IS NOT NULL
ORDER BY generated_at DESC
LIMIT 5;
```

**Prove affected races no longer run with macro_ctx=None:**
```sql
-- All recent verdicts should now have regime annotations
SELECT COUNT(*) AS total,
       COUNT(*) FILTER (WHERE full_analysis->>'verdict_flags' IS NULL) AS missing_flags,
       COUNT(*) FILTER (WHERE full_analysis->>'verdict_flags' IS NOT NULL) AS has_flags
FROM velo_verdicts
WHERE generated_at > NOW() - INTERVAL '24 hours';
```
Target: `missing_flags = 0`, `has_flags > 0`.

---

*Report: NEXUS targeted audit — 5 queries, incremental persistence*  
*Commit: `edf21a7` — `reports/nxs_audit_final_2026-03-24.md`*  
*GitNexus: 7,215 nodes | 17,911 edges | 652 clusters | 300 flows*
