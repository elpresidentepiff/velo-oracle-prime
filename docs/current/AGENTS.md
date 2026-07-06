# AGENTS.md — Internal Agent Roles

Defines the functional roles an agent (or a human operator) plays when working in
this repo. These are role labels for handoff clarity, not separate running
processes — a single agent session typically moves through several roles in one
mission.

| Agent | Function |
|---|---|
| **Scout** | Finds evidence, artifacts, missing data. Reads existing reports, greps for prior work, checks whether an artifact already exists before claiming it doesn't. Never invents a file that isn't there — reports `MISSING_ARTIFACT` with the expected path instead. |
| **Analyst** | Interprets race/model/system signals once evidence is found. Applies `docs/current/MODEL_RESULT_REPORTING_LAW.md` — never collapses model rank, policy decision, and result into one claim. |
| **Builder** | Writes docs/code/tests under an explicit task contract (`ops/task_contracts/*.json`). Stays inside `allowed_paths`, never touches `forbidden_paths`, never introduces `forbidden_keywords` (e.g. unauthorized `supabase`/live-scoring calls). |
| **Auditor** | Checks safety, artifact proof, and schema risk before anything is called done. Runs `worktree_safety_runner.py`, `side_effect_sentinel.py`, `task_contract_runner.py` (chained via `governed_task_runner.py`) where the mission calls for it. |
| **Tribunal** | Reviews promotion/rejection decisions for any shadow model or doctrine candidate. Mirrors the VFU-12 Sigma Pattern Tribunal precedent: prosecute the pattern, produce a human-review queue, promote only to a dry-run watchlist — never straight to live. |
| **Archivist** | Updates docs, indexes, and registries after a mission closes — this file's own maintainer role. Keeps `docs/current/ARTIFACT_REGISTRY.md`, `docs/current/VFU_INDEX.md`, and `docs/current/ONE_TRUTH.md` in sync with what was actually built. |

## Required handoff fields

Every agent-to-agent (or agent-to-operator) handoff must include:

```
contract_id:    <task contract id, e.g. DOCS-01>
scope:          <what this handoff covers>
artifact_path:  <exact file(s) produced or MISSING_ARTIFACT + expected path>
evidence:       <source path/field/commit backing the claim>
risk_class:     <NO_LIVE_SCORING_CHANGE | NO_SUPABASE_WRITES | NO_TELEGRAM_SEND |
                 NO_MODEL_PROMOTION | or the specific risk if one was taken, with
                 explicit operator authorisation cited>
next_action:    <what the next agent/operator should do>
```

## How roles map to existing runtime tooling

| Role | Tooling |
|---|---|
| Scout / Auditor | `scripts/ops/velo_session_start_check.py`, `scripts/ops/worktree_safety_runner.py`, `scripts/ops/side_effect_sentinel.py` |
| Builder | `scripts/ops/task_contract_runner.py` (preflight + audit modes), `scripts/ops/governed_task_runner.py` (chains all three) |
| Analyst | `scripts/ops/run_results_sigma.py`, `scripts/ops/build_canonical_model_scorecard.py`, `scripts/ops/build_canonical_learning_events.py` |
| Tribunal | VFU Pattern Prosecutor / Sigma Pattern Tribunal lineage — see `docs/current/VFU_INDEX.md` (VFU-05, VFU-12) |
| Archivist | This documentation spine (`docs/current/*`), `data/current/*_latest.json` state files |

See `docs/current/GOVERNED_TASK_RUNNER.md`, `docs/current/TASK_CONTRACT_RUNNER.md`,
`docs/current/SIDE_EFFECT_SENTINEL.md`, and `docs/current/WORKTREE_SAFETY_RUNNER.md`
for the full mechanics behind each safety gate referenced above.
