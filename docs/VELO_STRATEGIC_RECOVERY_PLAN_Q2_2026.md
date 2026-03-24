# VÉLØ STRATEGIC RECOVERY PLAN — Q2 2026
**Status:** ACTIVE RECOVERY
**Author:** VOX / NEXUS
**Date:** 2026-03-23
**Classification:** Internal — Operational

---

## 1. EXECUTIVE TRUTH

Architecture is ahead of execution. Operational maturity is the bottleneck. VÉLØ is alive but under operational stabilization.

**What is true:**
- VÉLØ PRIME scores races live on Railway (06:00 UTC daily)
- Sigma close loop fires correctly at 22:00 UTC
- Database is writing: velo_verdicts, sigma_audits, learned_patterns, pipeline_runs
- Ensemble design is sound: 7 specialist models, BHA macro regime, SQPE v17 base
- The architecture has been evaluated at 7/10 by independent audit

**What is broken:**
- Two of three FastAPI prediction endpoints are broken
- Hardcoded Linux paths in model_ops/loader.py
- BHA macro parquet is missing — regime corrections are disabled
- sigma_audits has partial writes — learning loop's own audit trail is unreliable
- No integration tests for the core scoring path
- Pipeline_runs has known gaps on crash/failure paths

**The governing constraint:**
> No major new features before operational maturity improves.
> No live orchestrator wiring before scoring and sigma are trustworthy.
> No HK live work before UK production is hardened.
> All future work is ranked by operational leverage, not novelty.

---

## 2. CURRENT STATE ASSESSMENT

### Live Production (confirmed working)
| Component | Status | Last verified |
|---|---|---|
| velo-prime-scoring ( Railway) | LIVE | 2026-03-23 14:09 UTC |
| velo-results-sigma ( Railway) | LIVE | 2026-03-23 22:02 UTC |
| velo_verdicts writing | LIVE | 2026-03-23 292 verdicts |
| sigma_audits writing | LIVE | 2026-03-23 date/track populated |
| learned_patterns accumulating | LIVE | 20+ active patterns |
| Railway cron scheduling | LIVE | 06:00 / 22:00 UTC confirmed |

### Broken or Degraded
| Component | Severity | Fix owner |
|---|---|---|
| `/predict/quick` endpoint | BLOCKING | Engineering |
| `/predict/full` endpoint | BLOCKING | Engineering |
| BHA macro parquet missing | HIGH — silent score degradation | Engineering + Data |
| Hardcoded Linux paths (`model_ops/loader.py`) | HIGH — deployment fragility | Engineering |
| sigma_audits partial writes | MEDIUM — learning loop unreliable | Engineering |
| pipeline_runs gaps on crash | MEDIUM — observability gap | Engineering |
| No integration tests for scoring | MEDIUM — regression risk | Engineering |

### NEXUS Project Score: 5.4/10
| Category | Score | Gap |
|---|---|---|
| Innovation | 7 | Designed well |
| Architecture Soundness | 6 | Sound structure |
| Harmonious Complexity | 5 | Fragmented delivery |
| Build Quality | 5 | Technical debt |
| Operational Maturity | 4 | Main bottleneck |
| **Overall** | **5.4** | **Execution lagging design** |

---

## 3. PRIORITY LADDER

### PHASE 0 — Production Truth Fix
*Objective: Make the live system observable and reliable, not speculative.*

**0.1** Fix `/predict/quick` endpoint — broken in production
**0.2** Fix `/predict/full` endpoint — broken in production
**0.3** Remove hardcoded Linux paths from `model_ops/loader.py`
**0.4** Restore trustworthy pipeline_runs — close crash/failure gaps
**0.5** Prove sigma_audits reliability — full field population verified

*Gate: Live observability restored before any expansion work begins.*

---

### PHASE 1 — Scoring Hardening
*Objective: The scoring output is trustworthy and complete.*

**1.1** Deploy real BHA macro parquet to Railway
**1.2** Verify `macro_available=true` in live verdicts — prove regime corrections active
**1.3** Add integration tests for `score_race_velo_prime()`
**1.4** Review confidence thresholds — confirm distribution is not artificially skewed
**1.5** Prove region enforcement in DB — UK/IRE filtering at query level

*Gate: Scoring output verified complete and reliable before sigma work proceeds.*

---

### PHASE 2 — Learning Closure
*Objective: The feedback loop is trustworthy, not approximate.*

**2.1** Fix sigma_audits — all fields populated, no partial writes
**2.2** Verify velo_post_race_reviews population — confirm reads and writes are balanced
**2.3** Confirm learned_patterns / SENTIENT_STATE_BACKUP are readable and accurate
**2.4** Ghost fields decision — `miss_category` and `miss_evidence`: wire or explicitly quarantine
**2.5** Sigma close produces clean audit trail for every race

*Gate: Learning output is trustworthy before any new intelligence work begins.*

---

### PHASE 3 — Controlled Intelligence Expansion
*Objective: Expand only from a hardened, trustworthy base.*

**3.1** Wire 5-agent orchestrator into stable pipeline — not before Phase 0–2 complete
**3.2** Phase 2 sentient modifiers — bounded, audited, not before Phase 2 verified
**3.3** HK research scoring — active build lane, not live production lane
**3.4** France — archive only, no active build

*Gate: Phase 3 begins only when Phase 2 is verified closed.*

---

## 4. WHAT WE ARE NOT DOING NOW

Stated plainly, not as limitations but as active decisions:

**We are not adding new specialist models** — the 7 we have are substantive. More signals on an unstable base compound error.

**We are not wiring the 5-agent orchestrator into an unstable base** — complexity added to a fragmented system is risk, not progress.

**We are not treating staged schema as live intelligence** — `miss_category` and `miss_evidence` are future infrastructure. They do not influence scoring today. They will be wired when Phase 2 is verified.

**We are not expanding production beyond UK/IRE** — HK and France are research lanes. UK/IRE is the only production lane. That separation is not a suggestion.

**We are not mistaking git truth for production truth** — a fix in git is not a fix in production. A deploy is not a verified run. A report is not proof.

**We are not treating display fields as operational intelligence** — TRUTH_REGISTRY marks display-only fields explicitly. That distinction is policy.

---

## 5. PASS / FAIL GATES PER PHASE

### Phase 0 — Production Truth Fix

| Item | Pass Criteria | Verification | Fail / Rollback |
|---|---|---|---|
| `/predict/quick` | Returns valid JSON with `velo_prime_prob` for test race | `curl` against live Railway endpoint | Revert last deploy; do not proceed |
| `/predict/full` | Returns valid JSON with `full_analysis` for test race | `curl` against live Railway endpoint | Revert last deploy; do not proceed |
| Hardcoded paths | `model_ops/loader.py` uses env var or relative path | Code review + successful model load on redeploy | Freeze scoring service; no new deploys |
| pipeline_runs | All service starts write a completed row | `SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 10` | Audit every gap; block deploy until resolved |
| sigma_audits reliability | 100% of race_ids have date, track, outcome, miss_reason populated | `SELECT COUNT(*) WHERE date IS NULL` — expect 0 | Sigma close frozen; manual review required |

---

### Phase 1 — Scoring Hardening

| Item | Pass Criteria | Verification | Fail / Rollback |
|---|---|---|---|
| BHA macro parquet | `macro_available=true` in 100% of recent verdicts | `SELECT full_analysis->>'macro_available' FROM velo_verdicts` | Revert to fallback; do not claim regime corrections active |
| Regime corrections active | `regime_label` and `verdict_flags` populated in recent verdicts | Spot-check 5 AW or low-grade handicap races | Continue with fallback; escalate |
| Integration tests | `pytest tests/test_score_race_velo_prime` — 100% pass | CI run or manual pytest | No scoring deploy without passing tests |
| Confidence threshold review | Distribution reviewed; no artificial skew confirmed | `SELECT confidence_level, COUNT(*) FROM velo_verdicts GROUP BY 1` | Investigate before next scoring cycle |
| Region enforcement | UK/IRE queries return only UK/IRE races; HK/FR excluded from production | `SELECT DISTINCT region FROM velo_verdicts` | Remove filter if over-restrictive; add if absent |

---

### Phase 2 — Learning Closure

| Item | Pass Criteria | Verification | Fail / Rollback |
|---|---|---|---|
| sigma_audits full population | `top_strike_correct`, `value_correct`, `miss_reason`, `decision_tier` all populated for every race | Query for NULLs in each column | Freeze sigma close; audit every NULL row |
| velo_post_race_reviews | Reviews are being written and read correctly | Count matches race count; morning_cockpit reads successfully | Investigate reader/writer gap |
| learned_patterns accuracy | Patterns reflect recent sigma audits; no stale data | Spot-check 5 recent patterns against sigma_audits | Clear stale patterns; require manual re-approval |
| Ghost fields decision | `miss_category`/`miss_evidence` — either wired to a reader or explicitly quarantined in TRUTH_REGISTRY | Code search for all readers | Quarantine confirmed or wire confirmed — no middle state |
| Sigma audit trail | Every sigma close run writes a clean log; no silent skips | Railway logs show clean `completed` for every run | Investigate every non-clean exit |

---

### Phase 3 — Controlled Expansion

| Item | Pass Criteria | Verification | Fail / Rollback |
|---|---|---|---|
| Orchestrator wiring | Live A/B test on 10% of races; results tracked | sigma_audits comparison between orchestrator and baseline | Revert to baseline if degradation detected |
| Phase 2 sentient modifiers | Bounded modifier; one doctrine family; full audit log | TRUTH_REGISTRY updated; audit log readable | Hard cap triggered; modifier auto-disabled |
| HK research scoring | HK races scored in separate schema; not exposed as production | `velo_verdicts HK region count` = 0 | HK scoring frozen; escalate |
| France archive | France data stored raw; no active scoring | France rows in `races` table have no `velo_verdicts` | France scoring banned; architecture enforcement |

---

## 6. OWNER / DEPENDENCY / PROOF TABLE

| Item | Owner | Dependencies | Proof | Status |
|---|---|---|---|---|
| Fix `/predict/quick` | Engineering | None | `curl` live endpoint returns valid response | BACKLOG |
| Fix `/predict/full` | Engineering | None | `curl` live endpoint returns valid response | BACKLOG |
| Remove hardcoded paths | Engineering | None | Model loads on non-Linux Railway deploy | BACKLOG |
| pipeline_runs gaps | Engineering | None | All recent runs show completed rows | BACKLOG |
| Deploy BHA macro parquet | Engineering + Data | BHA data source | `macro_available=true` in live verdicts | BACKLOG |
| Integration tests | Engineering | Phase 0 complete | pytest 100% pass | BACKLOG |
| sigma_audits full population | Engineering | Phase 0 | `SELECT` shows 0 nulls in key columns | BACKLOG |
| Ghost fields decision | Engineering | Phase 2 data verified | Code or TRUTH_REGISTRY updated | BACKLOG |
| Orchestrator wiring | Engineering | Phase 0, 1, 2 all verified | A/B test results vs baseline | BACKLOG |
| HK research lane | Engineering | Phase 0 stable | HK scored in separate schema, not prod | BACKLOG |

---

## 7. 30 / 60 / 90 DAY TIMELINE

### 30 Days — Foundation
- [ ] Fix `/predict/quick` — return live response
- [ ] Fix `/predict/full` — return live response
- [ ] Remove hardcoded Linux paths
- [ ] Deploy BHA macro parquet (or prove fallback is acceptable short-term)
- [ ] Prove `macro_available` in live verdicts
- [ ] Close pipeline_runs gaps
- [ ] sigma_audits: zero nulls in date, track, outcome, miss_reason

**Gate to 60-day:** Phase 0 complete. Live observability restored. Scoring output trustworthy.

---

### 60 Days — Hardening
- [ ] Integration tests for `score_race_velo_prime()` — passing
- [ ] Confidence threshold review — distribution documented
- [ ] Region enforcement verified in DB
- [ ] learned_patterns / SENTIENT_STATE_BACKUP — accuracy verified
- [ ] velo_post_race_reviews — reads and writes confirmed balanced
- [ ] Ghost fields — wired or quarantined (decision made and implemented)

**Gate to 90-day:** Phase 1 and Phase 2 complete. Learning loop trustworthy.

---

### 90 Days — Controlled Expansion
- [ ] Orchestrator wiring — A/B test running
- [ ] Phase 2 sentient modifiers — spec written, bounded, audited
- [ ] HK research scoring — active in research lane only
- [ ] France — archive confirmed, no production scoring

**Gate:** Phase 3 begins only from a verified stable base.

---

## 8. FREEZE CONDITIONS

If any of the following occur, the relevant phase is immediately frozen and no new work begins until resolved:

| Condition | Frozen | Until |
|---|---|---|
| Scoring service crashes on Railway | Phase 0 + 1 + 2 + 3 | Root cause identified and fixed |
| sigma_audits write failure on 3 consecutive nights | Phase 2 | sigma_audits confirmed writing correctly |
| Hardcoded path regression | Phase 0 + 1 + 2 + 3 | Path fixed and verified |
| BHA macro parquet not deployed after 30 days | Phase 1 | Parquet deployed and `macro_available=true` confirmed |
| `miss_category`/`miss_evidence` left unwired after 60 days | Phase 2 | Decision made and implemented |
| Any Phase 3 work causes degradation in Phase 0/1 verified metrics | Phase 3 | Revert; root cause analysis complete |

**Freeze rule:** Any team member can invoke a freeze. The burden of proof is on continuation, not on pause.

---

## APPENDIX: METRIC BASELINE (as of 2026-03-23)

| Metric | Value | Source |
|---|---|---|
| velo_verdicts today | 292 | Supabase |
| Confidence distribution | 65% low / 9% normal / 11% high | Supabase |
| pipeline_runs | Last: 2026-03-23 14:09 UTC | Supabase |
| sigma_audits | Last: 2026-03-23 22:02 UTC, 23 races | Supabase |
| learned_patterns | 20+ active | Supabase |
| NEXUS score | 5.4/10 overall | NEXUS audit |

---

*Document: VELO_STRATEGIC_RECOVERY_PLAN_Q2_2026.md*
*Version: 1.0 — 2026-03-23*
*Status: Active — review at each phase gate*
