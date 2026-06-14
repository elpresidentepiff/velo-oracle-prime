# Council Nightly Enforcement Audit

**Generated:** 2026-05-22  
**Scope:** 3-day test — May 20 (contaminated), May 21 (first clean), May 22 (second clean)

---

## Verdict Summary

| Date | Verdict | Learning Gate | Correct? |
|---|---|---|---|
| 2026-05-20 | **QUARANTINE_DAY** | BLOCKED | YES |
| 2026-05-21 | WATCH_ONLY | WATCH | YES (conservative) |
| 2026-05-22 | WATCH_ONLY | WATCH | YES (conservative) |

---

## May 20 — QUARANTINE_DAY (Expected)

- Contaminated run_ids: `32cc27f9`, `847964a6`
- Flatline count: **6 fully-uniform races**
- Blocking agents: DATA AUDITOR (SOURCE_CONTAMINATED), FLATLINE GATE (FLATLINE_BLOCK)
- sigma_audits truth rows: **preserved — not blocked**
- Learning: **BLOCKED**
- Verdict: **CORRECT** — the machine correctly refuses to learn from contaminated evidence

---

## May 21 — WATCH_ONLY (Expected)

- Contaminated run_ids: none
- Flatline count: 0
- Watch reasons: SOURCE_UNKNOWN (source field not in verdict JSON), SIGMA_MISSING (sigma_results file not found)
- sigma_audits truth rows: preserved in DB — never blocked
- Learning: conservatively WATCH_ONLY
- Verdict: **CORRECT** — clean day, no quarantine, conservative due to known gap

---

## May 22 — WATCH_ONLY (Expected)

- Contaminated run_ids: none
- Flatline count: 0
- Watch reasons: SIGMA_MISSING, MIDPRICE_NOT_BUILT
- sigma_audits truth rows: preserved in DB — never blocked
- Learning: conservatively WATCH_ONLY
- Verdict: **CORRECT** — clean day, no quarantine, conservative due to known gap

---

## Enforcement Checks

| Check | Result |
|---|---|
| Contaminated day quarantined | PASS |
| Clean days NOT quarantined | PASS |
| sigma_audits truth never blocked | PASS |
| Learning blocked on contaminated day | PASS |
| Contamination isolated to May 20 only | PASS |
| Council MISSING → Mission Control blocks learning | PASS |

---

## Known Gap: SIGMA_MISSING on Clean Days

**Issue:** Council reads `data/sigma_results_{date_und}.json` but sigma writes to Supabase `sigma_audits` table directly, not a local JSON file.

**Impact:** Clean days show WATCH_ONLY instead of PASS_TO_LEARNING. Not a false quarantine — this is conservative behaviour. Sigma truth is in the DB.

**Fix required:** Wire `run_results_sigma.py` to write `data/sigma_results_{date_und}.json` after sigma close, OR update `SigmaCoverageAgent` to query `sigma_audits` DB directly.

Until fixed: clean days will remain WATCH_ONLY, which blocks learning consumption. This is safe but overly conservative.

---

## No-Tribunal Rule

If Council verdict is missing or NOT_RUN for a date, Mission Control marks learning gate as BLOCKED by default (conservative). The `_load_last_council_verdict()` function in `update_mission_control.py` returns `NOT_RUN` when no council JSON exists, which downstream gates treat as non-permissive.

---

## Overall

**ENFORCEMENT_WORKING.** The tribunal correctly isolates contaminated evidence, preserves sigma truth, and applies conservative gates on clean days. The SIGMA_MISSING gap is the only open item — it prevents PASS_TO_LEARNING from firing on legitimate clean days.
