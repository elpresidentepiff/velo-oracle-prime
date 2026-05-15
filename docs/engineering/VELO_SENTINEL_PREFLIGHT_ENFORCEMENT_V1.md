# VÉLØ SENTINEL PREFLIGHT ENFORCEMENT V1

## Purpose

Defines the enforcement contract for VÉLØ operator commands that carry write-side effects.
Every `--execute` command must pass a Safety Sentinel preflight evaluation before proceeding.
This document records the command matrix, classification rules, allowed overrides, exit codes,
and test cases. It does not activate any new code — V1 enforcement is a design contract.

## Classification Hierarchy

```
SAFE   → proceed immediately
WARN   → proceed only with --allow-warn flag (operator acknowledges)
BLOCK  → hard stop. No CLI override in V1. Fix the underlying condition first.
```

BLOCK is not negotiable. The sentinel cannot be bypassed with any flag in V1.
If a BLOCK fires in automation (Railway cron), the worker exits 1 and Telegram
must receive a BLOCK alert — no silent swallow.

---

## Command Matrix

| Command | Sentinel call | BLOCK on | WARN on | --allow-warn accepted |
|---|---|---|---|---|
| `daily-eod --execute` | `evaluate(date, command="daily-eod", learning_requested=True)` | Any BLOCK check | repo_dirty, runbook_docs_dirty | Yes |
| `predict --execute` | `evaluate(date, command="predict")` | Any BLOCK check + prediction_overwrite_risk | repo_dirty, runbook_docs_dirty | Yes |
| `sigma --execute` | `evaluate(date, command="sigma")` | forbidden_paths_clean, secret_files_clean, verify_false_absent | repo_dirty | Yes |
| `learn-shadow --execute` | `evaluate(date, command="learn-shadow", learning_requested=True)` | Any BLOCK check + sigma_truth_ready | repo_dirty, runbook_docs_dirty | Yes |
| `bulk-shadow-consume --execute` | `evaluate(date, command="bulk-shadow-consume", learning_requested=True)` | Any BLOCK check + sigma_truth_ready | repo_dirty | Yes |

---

## BLOCK Checks (hard stop — all commands)

These checks fire on every command. If any returns FAIL, classification = BLOCK.

| Check | Condition that triggers BLOCK | What to fix |
|---|---|---|
| `contaminated_shadow_target` | `target_state == "shadow_full_train_v1"` | Change target to `shadow_full_train_v2` |
| `live_state_git_clean` | `data/sentient_state.json` in modified_paths | Revert or commit the sentient state file |
| `consumed_live_zero` | `velo_learning_events.consumed_live > 0` | Investigate consumed_live rows before proceeding |
| `forbidden_paths_clean` | Any `FORBIDDEN_EXACT_PATHS` or `FORBIDDEN_PREFIX_PATHS` modified | Revert or commit forbidden file changes |
| `secret_files_clean` | `.env`, `*.key`, `credentials.json`, `*.pem`, `*.p12` in modified/staged | Remove secret files from working tree |
| `verify_false_absent` | `verify=False` or `verify = False` found in any changed script | Remove insecure TLS bypass |
| `new_executable_scripts_staged` | New `.py`, `.sh`, `.ps1`, `.bat` staged but not reviewed | Commit new scripts through a reviewed commit, not a hotpath add |

### Command-specific BLOCK checks

| Command | Additional BLOCK checks |
|---|---|
| `predict --execute` | `prediction_overwrite_risk` — BLOCK if prediction file for this date already exists |
| `daily-eod --execute` | `approved_shadow_target` — BLOCK if `target_state != "shadow_full_train_v2"` |
| `learn-shadow --execute` | `sigma_truth_ready` — BLOCK if `results_races == 0` or `sigma_audits == 0` |
| `bulk-shadow-consume --execute` | `sigma_truth_ready` — BLOCK if sigma not complete for all dates in scope |

---

## WARN Checks (--allow-warn required)

These checks fire but do not hard-stop. The operator may acknowledge and proceed.
In V1, WARN is logged but does not block Railway automation — only human-driven
`--execute` commands must pass the `--allow-warn` flag check.

| Check | Condition | Typical cause | Safe to proceed? |
|---|---|---|---|
| `repo_dirty` | Uncommitted changes exist | Runtime artifacts, local data files | Usually yes — check modified_paths first |
| `runbook_docs_dirty` | Governance docs modified but not committed | Doc drafts in progress | Yes if docs are WIP and not code |

### Approved WARN Cases

The following dirty-file states are acceptable under `--allow-warn`:

| Modified file pattern | Verdict |
|---|---|
| `data/safety_sentinel/` | SAFE — runtime output |
| `data/reports/` | SAFE — audit output |
| `data/racing_post_features/` | SAFE — local adapter output, never committed |
| `docs/engineering/*.md` (governance drafts) | SAFE — WIP docs |
| `data/cashrun_report_*.csv` | SAFE — daily scoring artifact |
| `data/velo_prime_verdicts_*.json` | SAFE — prediction output |
| `data/industry_selections_*.json` | SAFE — RP ingestion output |
| Any file in `app/services/safety_sentinel.py` | SAFE — sentinel itself |

The following dirty-file states are NOT acceptable even with `--allow-warn`:

| Modified file pattern | Verdict |
|---|---|
| `data/sentient_state.json` | NEVER — triggers BLOCK, not WARN |
| `config/weights.json` | NEVER — forbidden path, triggers BLOCK |
| `app/services/velo_prime_service.py` | NEVER — forbidden path |
| `scripts/run_prime_today.py` | NEVER — forbidden path |
| `scripts/send_telegram_summary.py` | NEVER — forbidden path |

---

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Preflight SAFE or WARN+allowed — command proceeds |
| 1 | Preflight BLOCK — command halted, operator must fix |
| 2 | Preflight WARN — `--allow-warn` not provided, command halted |

In Railway automation: exit code 1 must trigger a BLOCK alert. Exit code 2 means
the cron job did not pass the flag — investigate the cron invocation.

---

## Artifact Paths

| Artifact | Path |
|---|---|
| Dated preflight report | `data/safety_sentinel/YYYY-MM-DD_preflight.json` |
| Latest preflight report | `data/safety_sentinel/latest.json` |
| Sentinel module | `app/services/safety_sentinel.py` |
| Sentinel evaluate() | `SafetySentinel.evaluate(date, command, target_state, learning_requested)` |

---

## Test Cases

| # | Scenario | Expected classification | Expected next command |
|---|---|---|---|
| T1 | Clean repo, sigma PASS, target=v2 | SAFE | daily-eod proceeds |
| T2 | `data/sentient_state.json` modified | BLOCK | Revert sentient state |
| T3 | `target_state=shadow_full_train_v1` | BLOCK | Change target to v2 |
| T4 | Dirty repo (runtime artifacts only), sigma PASS | WARN | Proceed with --allow-warn |
| T5 | `verify=False` added to changed script | BLOCK | Remove insecure bypass |
| T6 | Prediction file exists for today, command=predict | BLOCK | Do not overwrite — use --skip-predict or confirm intentional |
| T7 | Sigma WAITING (results_races=0), command=learn-shadow | BLOCK | Wait for results |
| T8 | Sigma PARTIAL (results_races>0, sigma_audits=0), command=daily-eod | WARN via Mission Control route | Rerun sigma first |
| T9 | `.env` in staged files | BLOCK | Remove secret from staging |
| T10 | New `.py` script staged, not reviewed | BLOCK | Commit via reviewed path, not --execute path |

---

## V1 Scope Constraints

```
No automatic escalation to Telegram on BLOCK — operator responsibility in V1
No automatic rerun on WARN — operator must re-invoke with --allow-warn
No per-command WARN threshold relaxation — all commands share the same WARN checks
No override flag for BLOCK — period
SENTINEL BLOCK = hard stop, operator intervention required every time
```

---

## Integration Point — Mission Control

Mission Control (`scripts/velo_mission_control.py`) reads the latest sentinel report
and surfaces the classification as `safety_classification` in its output. Mission Control
does not re-run the sentinel — it reads the pre-written report artifact. The sentinel
must be run explicitly before any `--execute` command, or invoked by the Mission Control
preflight wrapper when that is built.

---

## Version History

| Version | Date | Changes |
|---|---|---|
| V1 | 2026-05-15 | Initial spec. Five commands. BLOCK/WARN/SAFE matrix. Exit codes. 10 test cases. |
