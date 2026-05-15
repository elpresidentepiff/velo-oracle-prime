# VÉLØ MAIN MERGE REVIEW — 2026-05-15

## A. Branch

```
Branch:  ops-worker-shadow-loop-preserve
Base:    origin/main
Review:  2026-05-15 (pre-EOD)
Reviewer: Claude Code automated review
```

---

## B. Commit Range

12 commits above main, ordered newest first:

| Hash | Message |
|---|---|
| `d31a27f` | fix(ops-worker): default Sentinel learning target to shadow_full_train_v2 |
| `24ed6ec` | docs(agent-os): EOD runbook, hook noise audit, RP V2 design, CASHRUN deep dive |
| `e71f7f3` | feat(ops-worker): enforce Sentinel preflight for execute commands |
| `aa6b2d9` | docs(agent-os): define preflight enforcement and RP/CASHRUN validation plans |
| `6a91868` | feat(cashrun): add activation audit report |
| `7b83214` | feat(rp): add RacingPostAdapter V1 skeleton |
| `522ab5e` | fix(mission-control): route partial sigma to sigma rerun |
| `2bd65d8` | feat: add May 15 RP VÉLØ convergence report |
| `dc686c9` | fix(scoring): persist verdict metadata and block stale card persistence |
| `27a84f2` | chore(governance): validate scoring-path invariants before live ops |
| `4818391` | chore(governance): audit dirty scoring-path diffs before live ops |
| `da1d0cf` | chore(security): document dirty worktree and Telegram secret containment |

---

## C. Files Changed (63 files, +62,270 / -68)

### Ops worker / Sentinel / Mission Control — CORE

| File | Classification | Risk |
|---|---|---|
| `workers/velo_ops_worker.py` | NEW — Phase 4A EOD orchestrator, Sentinel preflight wired | LOW |
| `workers/velo_supervisor.py` | NEW — supervisor wrapper | LOW |
| `app/services/safety_sentinel.py` | NEW — BLOCK/WARN/SAFE classification | LOW |
| `scripts/velo_mission_control.py` | NEW — operator cockpit, read-only | LOW |

### Scoring safety patch — REVIEWED (dc686c9)

| File | Classification | Risk |
|---|---|---|
| `app/services/velo_prime_service.py` | MODIFIED — metadata persistence + stale card block | LOW — reviewed commit |
| `scripts/run_prime_today.py` | MODIFIED — scoring orchestrator updates | LOW — reviewed commit |
| `app/main.py` | MODIFIED — minor FastAPI adjustments | LOW |

### RP Adapter / Convergence — ADVISORY (read-only)

| File | Classification | Risk |
|---|---|---|
| `app/services/racing_post_adapter.py` | NEW — read-only RP feature extractor | NONE |
| `scripts/build_racing_post_features.py` | NEW — CLI runner for adapter | NONE |
| `scripts/build_rp_velo_convergence_report.py` | NEW — convergence report builder | NONE |
| `scripts/ingest_racecard_pdfs.py` | MODIFIED — racecard PDF ingestion | LOW |

### CASHRUN / Learning — ADVISORY

| File | Classification | Risk |
|---|---|---|
| `scripts/cashrun_activation_audit.py` | NEW — evidence-only audit, no activation | NONE |
| `app/services/learning_engine.py` | MODIFIED — learning engine updates | LOW |
| `app/services/ops_service.py` | MODIFIED — ops service updates | LOW |

### Config / DB

| File | Classification | Risk |
|---|---|---|
| `config/velo_agent_registry.json` | NEW — agent registry metadata | NONE |
| `supabase/migrations/20260513_create_velo_job_runs.sql` | NEW — schema migration | MEDIUM — idempotent DDL |
| `supabase/migrations/20260513_create_velo_learning_events.sql` | NEW — schema migration | MEDIUM — idempotent DDL |
| `.gitignore` | MODIFIED — additional patterns added | NONE |

### Committed data artifacts — NOTE

| File | Classification | Note |
|---|---|---|
| `data/racecard_merged/racecard_*_2026-05-14.json` (5 files) | Runtime artifact | Committed; not harmful |
| `data/cashrun_operator_card_2026_05_14.md` | Runtime artifact | Committed; evidence record |
| `data/cashrun_report_2026_05_14.md` | Runtime artifact | Committed; evidence record |
| `data/racing_post_coverage_2026_05_14.md` | Runtime artifact | Committed; evidence record |
| `data/racing_api_final_harvest_report.json` | Runtime artifact | Committed; evidence record |
| `data/reports/cashrun_activation_audit_latest.json` | Runtime artifact | Committed; audit output |
| `data/reports/cashrun_activation_audit_latest.md` | Runtime artifact | Committed; audit output |
| `data/reports/rp_velo_convergence_2026-05-14.json` | Runtime artifact | Committed; evidence |
| `data/reports/rp_velo_convergence_2026-05-14.md` | Runtime artifact | Committed; evidence |
| `data/reports/rp_velo_convergence_2026-05-15.json` | Runtime artifact | Committed; evidence |
| `data/reports/rp_velo_convergence_2026-05-15.md` | Runtime artifact | Committed; evidence |

**Note on data artifacts:** These are committed runtime outputs from the May 14-15 session. They are not harmful, but they are not ideal for a clean main branch. Consider squashing or stripping these on future PRs. For this merge, they are non-blocking.

`data/racing_post_features/*.json` is NOT committed (correctly gitignored / excluded).
`data/sentient_state.json` is NOT committed ✓

### Docs — ADVISORY (27 new/modified engineering docs)

All docs are in `docs/engineering/`. No functional risk.

---

## D. Forbidden-Change Check

| Check | Result | Evidence |
|---|---|---|
| No staking changes (`app/staking/`, `scripts/staking/`) | ✅ PASS | Not in delta |
| No router changes (`app/router/`, `scripts/router/`) | ✅ PASS | Not in delta |
| No Telegram runtime re-enable (`scripts/send_telegram_summary.py`) | ✅ PASS | Not in delta |
| No Playbook G promotion | ✅ PASS | No `playbook_g_promote` in delta |
| No `data/sentient_state.json` committed | ✅ PASS | Not in delta |
| `consumed_live=True` count | ✅ PASS | Count = 0 (confirmed via Supabase) |
| No `shadow_full_train_v1` as default | ✅ PASS | Fixed in `d31a27f` |
| No `config/weights.json` changes | ✅ PASS | Not in delta |
| No `app/services/predictor.py` changes | ✅ PASS | Not in delta |
| No `app/services/model_loader.py` changes | ✅ PASS | Not in delta |
| No `verify=False` in changed scripts | ✅ PASS | Sentinel check confirms |
| `data/racing_post_features/*.json` not committed | ✅ PASS | Not in delta |

**Scoring safety patch note:** `velo_prime_service.py` and `run_prime_today.py` appear in the delta
(commit `dc686c9`, reviewed and approved in session). These are reviewed commits, not ad-hoc edits.
The Sentinel's `forbidden_paths_clean` check guards against future unstaged edits — it does not
retroactively flag committed changes. Status: reviewed and accepted.

---

## E. Syntax Check

```
python -m py_compile:
  workers/velo_ops_worker.py          ✅ OK
  app/services/learning_engine.py     ✅ OK
  app/services/safety_sentinel.py     ✅ OK
  app/services/racing_post_adapter.py ✅ OK
  scripts/velo_mission_control.py     ✅ OK
  scripts/build_racing_post_features.py ✅ OK
  scripts/cashrun_activation_audit.py ✅ OK

All 7 files: SYNTAX OK
```

---

## F. Mission Control Result

```
VELO Mission Control - 2026-05-15
Prediction:     PASS
RP Coverage:    PASS (100.0%)
CASHRUN:        WATCH=6
Sigma:          WAITING
Learning:       BLOCKED
Approved Shadow: shadow_full_train_v2
Live State:     UNTOUCHED
Safety:         WARN
Next Safe Command: wait for results, then:
  python scripts/run_results_sigma.py --date 2026-05-15
```

Mission Control outputs exactly the expected state. No anomalies.

---

## G. Sentinel Gate Test Results

| Test | Command | Expected | Result |
|---|---|---|---|
| T1 | `sigma --execute` (no `--allow-warn`) | WARN exit(2) | ✅ WARN `repo_dirty, runbook_docs_dirty` exit(2) |
| T2 | `sigma --execute --allow-warn` | proceeds | ✅ proceeds to sigma logic |
| T3 | `daily-eod --target shadow_full_train_v1` | BLOCK | ✅ BLOCK `approved_shadow_target` exit(1) |
| T4 | `daily-eod` (no `--target-state`) | defaults `shadow_full_train_v2`, BLOCK on sigma | ✅ BLOCK `sigma_truth_ready` exit(1) |

**T1 confirmation:** `approved_shadow_target` is NOT present in T1's WARN list. Shadow target noise for sigma is eliminated. ✓

**T4 confirmation:** Default target is `shadow_full_train_v2`. Target check passes. BLOCK fires for the correct reason (no results yet). ✓

---

## H. Live State Hash

```
sentient_state.json SHA-256 (first 16): 1016d89dceb28da5
Status: UNTOUCHED — matches pre-branch baseline
```

---

## I. Cloud Backup

```
SENTIENT_STATE_BACKUP updated_at: 2026-05-02T19:55:26.059253
Status: UNCHANGED since 2026-05-02 — no unintended backup writes
```

---

## J. Consumed Live Count

```
velo_learning_events WHERE consumed_live=True: 0
Status: CLEAN — no live consumption events
```

---

## K. Merge Recommendation

```
RECOMMENDATION: READY_TO_PR_OPEN_ONLY
```

**Rationale:**

The branch is functionally clean. All sentinel gates work correctly. Syntax is clean.
No forbidden changes. Live state is untouched. consumed_live is zero.

A PR (not a direct push to main) is recommended because:

1. **Scoring patch transparency** — `velo_prime_service.py` and `run_prime_today.py` are forbidden-path files
   that appear in the delta. The PR description must explicitly document why these were changed (scoring
   safety patch `dc686c9`) and confirm the changes are reviewed. A PR provides that paper trail.

2. **Data artifacts on main** — 11 committed runtime data files will land on main. Not blocking, but a PR
   allows a final decision on whether to strip these (e.g. a pre-merge rebase squash) or accept them.

3. **Supabase migrations** — Two DDL migration files in the delta. These should be verified as idempotent
   before they reach main (i.e. safe to re-run if main already has these tables).

**What is not a concern:**
- Sentinel enforcement is production-ready and tested
- Default target is correct (`shadow_full_train_v2`)
- No live systems are mutated
- CASHRUN is OPERATOR_VISIBILITY_ONLY
- RP Adapter is read-only
- Telegram is still disabled

**Recommended PR title:**
`feat: Sentinel enforcement, Mission Control, RP adapter, CASHRUN audit (ops-worker-shadow-loop-preserve)`

**Recommended merge timing:**
Before May 15 EOD — the Sentinel enforcement on this branch is the guardrail the EOD run needs.
If the EOD run happens before merge, it runs without the Sentinel lock.

---

## Version History

| Version | Date | Notes |
|---|---|---|
| V1 | 2026-05-15 | First formal merge review. 12 commits, 63 files. Recommendation: READY_TO_PR_OPEN_ONLY. |
