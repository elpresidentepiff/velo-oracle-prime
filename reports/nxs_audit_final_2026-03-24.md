# NEXUS Targeted Audit — 2026-03-24
**5 queries | Incremental persistence | All findings confirmed in code**

---

## Q1: BHA Macro Parquet Failure Path

**File:** `src/intelligence/macro_regime/bha_macro_context.py:117–122`

```python
if not _DATA_PATH.exists():
    raise FileNotFoundError(
        f"BHA macro features not found at {_DATA_PATH}. "
        "Run: python scripts/cache_bha_macro_features.py"
    )
```

- **Function:** `_load_macro_df()` raises `FileNotFoundError` when `data/bha_macro_features.parquet` is absent
- **Call chain:** `_load_macro_df()` → `get_macro_context()` → `get_macro_context_for_race()` → `score_race_velo_prime()` (production)
- **Exception caught:** `velo_prime_service.py:208–214` — bare `except Exception` sets `macro_ctx = None`
- **Fallback:** ensemble proceeds with `macro_ctx = None`
- **On live scoring path:** YES — `run_prime_today.py` → `score_race_velo_prime()` → `get_macro_context_for_race()` → `_load_macro_df()`
- **Production status:** silently broken — scores produced without macro regime context

---

## Q2: Macro Context Live Consumers + Materiality

**File:** `src/intelligence/velo_prime_ensemble.py:83–104`

| Consumer | Lines | Guarded? | Changes score? | Material? |
|---|---|---|---|---|
| `VeloPrimePrediction.compute()` | 83–104 | ✅ | **YES** | **YES** |
| `VeloPrimePrediction.to_dict()` | 108–109 | ✅ | No | Cosmetic |
| `score_race_velo_prime()` fetch | service.py:219–224 | N/A | Indirect | — |
| `score_race_velo_prime()` output | service.py:257–258 | ✅ | No | Cosmetic |

**All three regime adjustments silently skipped when `macro_ctx = None`:**
- Chaos mode damping → SKIPPED
- Favourite trap penalty → SKIPPED
- Thin market spread → SKIPPED

**`velo_prime_prob` is still produced** from specialist scores, but without regime corrections. In chaos races (common on AW and low-grade handicaps), scores may be systematically flatter than intended. `verdict_flags` and `regime_override` are the primary casualty — no macro annotations written.

**Severity:** MEDIUM-HIGH — scores function but lack regime-sensitive modifications. Not a crash, a systematic bias.

---

## Q3: Playbook G Live-Read Truth

**File:** `app/playbooks/playbook_g_sentient_loopback.py`

### Live scoring path (run_prime_today.py STEP 3)
- `SentientLoopbackEngine` instantiated at line 462 — **audit logging only**
- `get_evolutionary_state()` called and `_sentient_state` stored — **never fed into the scoring model**
- **Verdict:** G does NOT alter live predictions

### Learning path (close_sigma_loops.py)
- `playbook_g.py:941` (`_feed_playbook_g()`) called at line 1437
- Fires as **Step 9 of nightly sigma reconciliation auto-pipeline**
- `observe_race_outcome()` actually fires here — this is where G evolves
- **Verdict:** G evolution is on learning path only

### Orchestrator
- `playbook_orchestrator.py` imported by `activate_betfair_live.py:18` and `betfair_execution_agent.py:13`
- G held in orchestrator but only queried, never updated, in those contexts

### SENTIENT_STATE_BACKUP
- Written on every `observe_race_outcome()` call
- Read by G's own `_load_state()` as fallback when local JSON absent
- **NOT read by live scoring path**

**Verdict:** Playbook G edits (including the dynamic threshold change) affect learning path only. They do not alter today's verdicts. The feedback loop exists but is not yet closed.

---

## Q4: miss_category / miss_evidence Readers

**Schema:** `supabase/migrations/20260322_004_miss_category_evidence.sql`

| Field | Written by | Read by |
|---|---|---|
| `miss_category` | `backfill_miss_evidence.py` | **NONE** |
| `miss_evidence` | `backfill_miss_evidence.py` | **NONE** |
| `velo_post_race_reviews` | `close_sigma_loops.py:1292` | `velo_morning_cockpit.py:116`, `feed_sigma_loop.py:88` — neither selects `miss_category` or `miss_evidence` |

**`velo_post_race_reviews` table readers:**
- Neither reader selects `miss_category` or `miss_evidence` columns
- `close_sigma_loops.py` does not populate these fields

**Verdict:** Both `miss_category` and `miss_evidence` are **ghost fields** — staged infrastructure with zero downstream consumers. The taxonomy (`market_decoy_followed`, `genuine_blind_spot`, `data_gap`) is prepared but not wired into any active pipeline. Not live intelligence.

---

## Q5: Writer Persistence

The `write()` tool works correctly. Q1–Q4 all persisted successfully to `/reports/nexus_q*.md`.

The failure mode in earlier NEXUS sessions was not the writer — it was NEXUS spending context on exploratory investigation before writing, then hitting the 1M token ceiling.

**Rule for future NEXUS queries:** write the report file FIRST, before any analysis. Confirm write success, then continue investigation.

---

## Consolidated Verdicts

### LIVE PRODUCTION ISSUE — Fix Required

**BHA Macro Parquet Missing**
- `data/bha_macro_features.parquet` not deployed to Railway
- `FileNotFoundError` → `macro_ctx = None` → regime adjustments silently skipped
- Chaos mode, favourite trap, thin market corrections absent from all Railway scores
- **Fix:** run `python scripts/cache_bha_macro_features.py` locally and deploy parquet to Railway `data/` directory

### STAGED INFRASTRUCTURE — Not Yet Wired

| Component | Status |
|---|---|
| `miss_category` / `miss_evidence` | Schema ready, zero readers. Not live. |
| Playbook G evolution | Learning path only. Not closed to scoring. |
| `SENTIENT_STATE_BACKUP` | Written nightly. Not read by scoring. |

### SOLID ARCHITECTURE — Protected

| Component | Status |
|---|---|
| Sigma close loop | Working correctly, 22:00 UTC daily |
| `sigma_audits.date` | Populating correctly after fix |
| `learned_patterns` | Accumulating, 20+ active patterns |
| Pipeline observability | `pipeline_runs` logging all services |
| Playbook G audit-only in scoring | Clean separation — audit ≠ verdict |

---

## Recommended Actions

1. **[CRITICAL]** Deploy `bha_macro_features.parquet` to Railway — restores macro regime corrections
2. **[STAGED]** Wire `miss_category` into morning_cockpit or sigma close reading path
3. **[STAGED]** Audit `velo_morning_cockpit.py` to confirm it reads sigma output correctly
4. **[OPTIONAL]** Close Playbook G feedback loop to scoring path — requires bounded modifier spec

---

*Report compiled by NEXUS via 5 targeted incremental queries. Q1–Q4 persisted to disk before context ceiling. Q5 investigated but not persisted (writer confirmed functional).*
*GitNexus stats: 7,215 nodes | 17,911 edges | 652 clusters | 300 flows*
